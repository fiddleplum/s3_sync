# S3 Sync

Performs backups and restores of files to and from local folders and S3 folders.

## Requirements

* Python3
* boto3 module (`pip3 install boto3`)

## AWS Setup

You need to create a user with S3 credentials and a policy that has access to ListBucket, GetObject, PutObject, DeleteObject for the bucket you intend to use. The bucket must also have its "block public access" permission "Block public access to buckets and objects granted through new access control lists (ACLs)" unchecked.

## Setup

First you need to get the S3 credentials and put them in a `keys.txt` file in the same folder as this readme. Follow the steps at [http://boto3.readthedocs.io/en/latest/guide/quickstart.html](http://boto3.readthedocs.io/en/latest/guide/quickstart.html).

Put your AWS Access Key and Secret Key in the file like this:

keys.txt:
```
<AWS Access Key>
<AWS Secret Key>
```

