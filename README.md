# Docker compose for crunchy-cli

This is a docker compose setup for running [mloader](https://github.com/hurlenko/mloader) in a docker container. Prerequisites are `docker` and `docker compose`

# Usage

Set all required environment variables in the `.env` file. The `SECRET` variable is needed to download with mloader. The secret can be obtained by running the app in an emulator. I ran it on a M1 Mac with Android Studio via the device manager. Once it ran successfully for the first time open the device explorer and copy the file `/data/data/jp.co.shueisha.mangaplus/shared_prefs/config.xml`. In it, you will find the secret. Copy its value into the `.env` file. Don't forget to set a download directory or all files will be downloaded to the default directory `downloads` within this project directory.

Execute `docker-compose up` in the project directory to run the container. You can execute `docker compose up -d` if you want silent execution. Use `docker compose down` to stop the container. If the docker image has not been built yet, it will be on the first run. The created docker image contains everything needed to use mloader with its full potential. Define all download tasks in the file `./script/download.sh`. The container will start and execute every command in this file.

Example content for `script/download.sh` (insert you tasks after the variable checks):
```
#!/usr/bin/env bash

...

## Start ##
mloader https://mangaplus.shueisha.co.jp/titles/100017
## End ##

## Start ##
mloader https://mangaplus.shueisha.co.jp/titles/100012
## End ##
```

For further information about mloader visit the repository: https://github.com/hurlenko/mloader

# Troubleshooting

If your `secret` or the `app_version` is wrong, mloader will not work. You need to download the latest version of manga plus for android (apk file) and run it in an emulator (android studio). Once you have obtained the secret, insert the app_version and the secret into the .env file and try running again. 

Something worth mentioning: At the time this project was created the only way of using mloader to download mobile-app exclusive mangas was installing the develop branch of mloader and manipulating entries in the loader.py file. If mloader merges the new features into its main branch, it might be possible, that this project will not work anymore. 

# 📜 Disclaimer

This tool is **ONLY** meant for private use.

**You are entirely responsible for what happens to files you downloaded through mloader.**

# ⚖ License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0) - see the [LICENSE](LICENSE) file for more details.