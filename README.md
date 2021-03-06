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
* py\_lru\_cache

```bash
$ pip install wsgidav beautifulsoup js2py py_lru_cache
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

access the following web page to test.

    http://localhost:8080/mangapanda/

enjoy in your mobile device by using a comic reader that supports WebDAV streaming.

## Supported sites & its webdav root folders

* ~~mangafox.me (/mangafox)~~
* mangapanda.com (/mangapanda)
* marumaru.in (/marumaru)
* hitomi.la (/hitomi)
