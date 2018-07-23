# S3 Sync

Performs backups and restores of files to and from local folders and S3 folders.

## Requirements

* Python3
* boto3 module (`pip3 install boto3`)

## Setup

First you need to get the S3 credentials and put them in a `keys.txt` file in the same folder as this readme. Follow the steps at [http://boto3.readthedocs.io/en/latest/guide/quickstart.html](http://boto3.readthedocs.io/en/latest/guide/quickstart.html).

Put your AWS Access Key and Secret Key in the file like this:

keys.txt:
```
<AWS Access Key>
<AWS Secret Key>
```

