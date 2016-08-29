# comicdav

proxy to view comics(manga) as webdav file

## How to use

### 1. intall required modules

* wsgidav (webdav server)
* beautifulsoup
* js2py

```bash
$ pip install wsgidav beautifulsoup js2py
```

### 2. run server

* modify wsgidav configuration file to change the followings:
  - port number
  - user & password

```bash
$ wsgidav --config=./wsgidav.conf
```

### 3. connect to server

access the following web page to test

    http://localhost:8080/mangafox/

### 4. recommended clients

* iOS
  - comicglass ($ to support streaming)
  - aircomix ($ to remove ad)
* Android
  - aircomix ($ to remove ad)
* Windows
  - no comic reader supporting webdav streaming yet
  - mount a related webdav folder as a drive first

## Supported Sites & its webdav root folders

* ~~mangafox.me (/mangafox)~~
* mangapanda.com (/mangapanda)
* hitomi.la (/hitomi)
* marumaru.in (/marumaru)
