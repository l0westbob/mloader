#!/bin/bash

if [[ -z "$APP_VERSION" ]];then
  echo "Set the app version in the .env file and run again" && exit 1
else
  # Set the app version in the loader.py file
  LINE=$(grep -n app_ver < /usr/local/lib/python3.11/site-packages/mloader/loader.py | cut -f1 -d":")
  sed -i "$LINE"'s/.*/    \"app_ver\": \"'"$APP_VERSION"'\",/g' /usr/local/lib/python3.11/site-packages/mloader/loader.py
fi;

if [[ -z "$SECRET" ]];then
  echo "Set the secret in the .env file and run again" && exit 1
else
  # Set the secret in the loader.py
  LINE=$(grep -n secret < /usr/local/lib/python3.11/site-packages/mloader/loader.py | cut -f1 -d":")
  sed -i "$LINE"'s/.*/    \"secret\": \"'"$SECRET"'\",/g' /usr/local/lib/python3.11/site-packages/mloader/loader.py
fi;

## Tell the user on the first run, that he did not create any download tasks! He has to read this file and comment out this line
echo "You don't have any download tasks defined OR you just created tasks and did not uncomment this line! Check the file ./script/download.sh and read the comments!" && exit 1

## Start ##
#mloader https://mangaplus.shueisha.co.jp/titles/100017
## End ##