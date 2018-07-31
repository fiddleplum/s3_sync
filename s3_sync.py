#!/usr/bin/env python3

import boto3
import mimetypes
import os
import re
import sys
import time

def log(message, error):
	print(message)

def get_ignore_list(local_folder):
	ignore_list = []
	if os.path.isfile(local_folder + 'ignore.txt'):
		with open(local_folder + 'ignore.txt') as ignore_file:
			for line in ignore_file:
				ignore_list.append(re.compile(line.strip()))
	return ignore_list

def create_manifest_from_local_folder(local_folder):
	manifest = {}
	ignore_list = get_ignore_list(local_folder)
	for root, directories, filenames in os.walk(local_folder):
		if not root.endswith('/'):
			root += '/'
		for filename in filenames:
			filename = (root + filename)[len(local_folder):].replace(os.sep, '/') # so it works in windows
			if filename == 'manifest.txt':
				continue
			ignoring = False
			for ignore_pattern in ignore_list:
				if ignore_pattern.match(filename):
					ignoring = True
					break
			if ignoring:
				continue
			manifest[filename] = int(os.path.getmtime(os.path.join(local_folder, filename)))
	return manifest

def create_manifest_from_s3_folder(s3_bucket, s3_prefix):
	manifest = {}
	for object_summary in s3_bucket.objects.filter(Prefix = s3_prefix):
		if object_summary.key == s3_prefix + 'manifest.txt':
			continue
		if object_summary.key == s3_prefix:
			continue
		object = object_summary.Object()
		if 'modified_time' in object.metadata:
			modified_time = int(object.metadata['modified_time'])
		else:
			modified_time = int(time.mktime(object_summary.last_modified.timetuple())) # just use the last modified time of the s3 file
		manifest[object_summary.key[len(s3_prefix):]] = modified_time
	return manifest

def get_manifest_from_s3_folder(s3_bucket, s3_prefix):
	manifest = {}
	try:
		log(s3_prefix, False)
		s3_bucket.download_file(s3_prefix + 'manifest.txt', 'manifest.txt')
		with open('manifest.txt') as manifest_file:
			for line in manifest_file:
				filename, modified_time = line.strip().split('\t')
				manifest[filename] = int(modified_time)
		os.unlink('manifest.txt')
	except Exception as e:
		log('The file manifest.txt did not exist in the s3 folder, so one is being created from the files.', False)
		manifest = create_manifest_from_s3_folder(s3_bucket, s3_prefix)
	return manifest

def upload_file_to_s3(s3_bucket, s3_prefix, local_folder, filename, modified_time):
	mimetype = mimetypes.guess_type(filename)[0]
	if mimetype == None:
		mimetype = 'application/octet-stream'
	extra_args = {
		'ACL': 'public-read',
		'ContentType': mimetype,
		'Metadata': {
			'modified_time': str(modified_time)
		}
	}
	s3_bucket.upload_file(local_folder + filename, s3_prefix + filename, ExtraArgs = extra_args)

def download_file_from_s3(s3_bucket, s3_prefix, local_folder, filename, modified_time):
	s3_bucket.download_file(s3_prefix + filename, local_folder + filename)
	os.utime(local_folder + filename, (modified_time, modified_time))

def put_manifest_to_s3_folder(s3_bucket, s3_prefix, local_folder, manifest):
	with open(local_folder + 'manifest.txt', 'w') as manifest_file:
		for filename, modified_time in manifest.items():
			manifest_file.write(filename + '\t' + str(modified_time) + '\n')
	upload_file_to_s3(s3_bucket, s3_prefix, local_folder, 'manifest.txt', time.time())

def backup(local_folder, s3_bucket, s3_prefix):
	s3_folder_manifest = get_manifest_from_s3_folder(s3_bucket, s3_prefix)
	local_folder_manifest = create_manifest_from_local_folder(local_folder)
	count = 0
	for filename in sorted(local_folder_manifest):
		modified_time = local_folder_manifest[filename]
		if (filename not in s3_folder_manifest) or (modified_time != s3_folder_manifest[filename]):
			log('Uploading ' + filename, False)
			try:
				upload_file_to_s3(s3_bucket, s3_prefix, local_folder, filename, modified_time)
			except FileNotFoundError as e:
				del local_folder_manifest[filename]
				continue
			s3_folder_manifest[filename] = modified_time
			count += 1
			if count == 100:
				put_manifest_to_s3_folder(s3_bucket, s3_prefix, local_folder, s3_folder_manifest)
				count = 0
	filenames_removed = []
	for filename in sorted(s3_folder_manifest):
		if filename not in local_folder_manifest:
			log('Removing ' + filename, False)
			s3_bucket.Object(s3_prefix + filename).delete()
			filenames_removed.append(filename)
	for filename in filenames_removed:
		del s3_folder_manifest[filename]
	put_manifest_to_s3_folder(s3_bucket, s3_prefix, local_folder, s3_folder_manifest)

def restore(local_folder, s3_bucket, s3_prefix):
	s3_folder_manifest = get_manifest_from_s3_folder(s3_bucket, s3_prefix)
	local_folder_manifest = create_manifest_from_local_folder(local_folder)
	for filename in sorted(s3_folder_manifest):
		modified_time = s3_folder_manifest[filename]
		if (filename not in local_folder_manifest) or (modified_time != local_folder_manifest[filename]):
			path = os.path.dirname(os.path.join(local_folder, filename))
			if not os.path.exists(path):
				os.makedirs(path)
			log('Downloading ' + filename, False)
			download_file_from_s3(s3_bucket, s3_prefix, local_folder, filename, modified_time)
			local_folder_manifest[filename] = modified_time
	filenames_removed = []
	for filename in sorted(local_folder_manifest):
		if filename not in s3_folder_manifest:
			log('Removing ' + filename, False)
			os.unlink(os.path.join(local_folder, filename))
			filenames_removed.append(filename)
	for filename in filenames_removed:
		del local_folder_manifest[filename]

def update_manifest(s3_bucket, s3_prefix):
	manifest = create_manifest_from_s3_folder(s3_bucket, s3_prefix)
	put_manifest_to_s3_folder(s3_bucket, s3_prefix, './', manifest)
	os.unlink('./manifest.txt')

if __name__ == '__main__':
	if len(sys.argv) < 3:
		log('Usage: s3_sync.py <operation> <s3 folder> <local folder>', True)
		log('Operations: backup, restore, update-s3-manifest', True)
		log('S3 folder format: <bucket name>/<folder path>', True)
		log('If you do update-s3-manifest, you don\'t need the local folder.', True)
		sys.exit(-1)

	# Get the arguments.
	operation = sys.argv[1]
	s3_folder = sys.argv[2]
	if len(sys.argv) == 4:
		local_folder = sys.argv[3]
		if not local_folder.endswith('/'):
			local_folder += '/'
	if not s3_folder.endswith('/'):
		s3_folder += '/'

	# Setup S3 from keys.txt.
	if os.path.isfile('keys.txt'):
		with open('keys.txt') as f:
			aws_access_key = f.readline().strip()
			aws_secret_key = f.readline().strip()
			session = boto3.session.Session(aws_access_key_id = aws_access_key, aws_secret_access_key = aws_secret_key)
			s3 = session.resource('s3')
	else:
		log('The key file keys.txt is missing.', True)
		sys.exit(-1)

	s3_bucket, *s3_prefix = s3_folder.split('/')
	s3_prefix = '/'.join(s3_prefix)
	s3_bucket = s3.Bucket(s3_bucket)

	# Do the operations.
	if operation == 'backup':
		backup(local_folder, s3_bucket, s3_prefix)
	elif operation == 'restore':
		restore(local_folder, s3_bucket, s3_prefix)
	elif operation == 'update-s3-manifest':
		update_manifest(s3_bucket, s3_prefix)
	else:
		log('Unknown operation.', True)
		sys.exit(-1)

	log('Completed.', False)
