# comicdav

Virtual WebDAV server for comic(manga) sites that allows the user to navigate the site in WebDAV structure.

There are many web sites that provide scanned comic images, but they are inconvinient to read in web page.<br/>
And also there are some comic readers designed for mobile devices that can access remote files in WebDAV server.<br/>
This virtual server gives benefit for the user to view comics with his favorite reader.

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
  - set username & password
  - set debug log

```bash
$ wsgidav --config=./wsgidav.conf
```

### 3. connect to server

access the following web page to test

    http://localhost:8080/mangapanda/

### 4. recommended clients

* iOS
  - aircomix ($ for ad free version)
  - comicglass ($ + $ for streaming)
* Android
  - aircomix ($ to remove ad)
  - comic reader mobi ($$)
* Windows
  - no comic reader supporting webdav streaming yet
  - mount a related webdav folder as a drive first

## Supported sites & its webdav root folders

* ~~mangafox.me (/mangafox)~~
* mangapanda.com (/mangapanda)
* marumaru.in (/marumaru)
* hitomi.la (/hitomi)
