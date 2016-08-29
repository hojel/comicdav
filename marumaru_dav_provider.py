# -*- coding: utf-8 -*-
"""
Proxy marumaru.in as virtual DAV
"""
import urllib
import urllib2
from BeautifulSoup import BeautifulSoup
from wsgidav.util import joinUri
from wsgidav.dav_provider import DAVProvider, DAVNonCollection, DAVCollection
from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN, HTTP_INTERNAL_ERROR,\
    PRECONDITION_CODE_ProtectedProperty
from wsgidav import util
import re
import base64
import js2py

__docformat__ = "reStructuredText"

_logger = util.getModuleLogger(__name__)

ROOT_URL = "http://marumaru.in"

req_hdrs = {
    "User-Agent":"Mozilla/5.0 (iPad; CPU OS 7_0 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Version/7.0 Mobile/11A465 Safari/9537.53",
    "Cookie":"",
}

#===============================================================================
# Virtual Collection
#===============================================================================
class RootCollection(DAVCollection):
    """Resolve top-level requests '/'."""
    btable = [
        ("update", 44),
        ("weekly",   28),
        ("biweekly", 29),
        ("monthly",  30),
        ("bimonthly",31),
        ("editorial",32),
        ("completed",33),
        ("short",27),
        ]
    
    def __init__(self, environ):
        DAVCollection.__init__(self, "/", environ)
        
    def getMemberNames(self):
        return [tname for tname,_ in self.btable]
    
    def getMember(self, name):
        # Handle visible categories and also /by_key/...
        for tname, tid in self.btable:
            if tname == name:
                url = ROOT_URL + "/?c=1/%d" % tid
                return ListPageCollection(joinUri(self.path, name), self.environ, url)
        return None


#===============================================================================
# List w/ pages
#===============================================================================
class ListPageCollection(DAVCollection):
    """ site: /?c=1/{id}"""
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
    
    def getDisplayInfo(self):
        return {"type": "Pages"}
    
    def getMemberNames(self):
        return map(str, range(1, 11))
    
    def getMember(self, name):
        if name.isdigit():
            url = self.url + "&p=%s" % name
            return ListCollection(joinUri(self.path, name), self.environ, url)
        _logger.error("unexpected member name, "+name)
        return None


class ListCollection(DAVCollection):
    """ site: /?c=1/{id}&p={num}"""
    ptn_url = re.compile("goHref\('(.*?)'\)")

    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.series = None
    
    def getDisplayInfo(self):
        return {"type": "List"}
    
    def getMemberNames(self):
        if self.series is None:
            self.parseSite()
        return [title for title,_ in self.series]
    
    def getMember(self, name):
        if self.series is None:
            self.parseSite()
        for title, url in self.series:
            if title == name:
                return SeriesCollection(joinUri(self.path, name), self.environ, url)
        return None

    def parseSite(self):
        _logger.debug(self.url)
        req = urllib2.Request(self.url, headers=req_hdrs)
        html = urllib2.urlopen(req).read()
        soup = BeautifulSoup(html)
        self.series = []
        for node in soup.findAll('div', {'class':'list'}):
            title = str(node.find('span', {'class':'subject'}).string)
            url = ROOT_URL + self.ptn_url.search(node['onclick']).group(1)
            self.series.append( (title, url) )


#===============================================================================
# SeriesCollection/EpisodeCollection
#===============================================================================
class SeriesCollection(DAVCollection):
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.episodes = None
    
    def getDisplayInfo(self):
        return {"type": "Series"}
    
    def getMemberNames(self):
        if self.episodes is None:
            self.parseSite()
        return [title for title,_ in self.episodes]
    
    def getMember(self, name):
        if self.episodes is None:
            self.parseSite()
        for title, url in self.episodes:
            if title == name:
                return EpisodeCollection(joinUri(self.path, name), self.environ, url)
        return None

    def parseSite(self):
        _logger.debug(self.url)
        req = urllib2.Request(self.url, headers=req_hdrs)
        html = urllib2.urlopen(req).read()
        soup = BeautifulSoup(html)
        self.episodes = []
        for node in soup.findAll('a', {'href':re.compile("/archives/")}):
            title = str(node.string)
            url = node.get('href')
            self.episodes.append( (title, url) )


class EpisodeCollection(DAVCollection):
    ptn_sucuri = re.compile("S\s*=\s*'([^']*)'")

    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url.replace("http://www.shencomics.com", "http://blog.yuncomics.com")
        self.cookie = None
        self.imgurls = None
    
    def getDisplayInfo(self):
        return {"type": "Episode"}
    
    def getMemberNames(self):
        if self.imgurls is None:
            self.parseSite()
        return [self.basename(url) for url in self.imgurls]
    
    def getMember(self, name):
        if self.imgurls is None:
            self.parseSite()
        for url in self.imgurls:
            fname = self.basename(url)
            if fname == name:
                return ImageFile(joinUri(self.path, name), self.environ, url, self.url, self.cookie)
        return None

    def parseSite(self):
        _logger.debug(self.url)
        req = urllib2.Request(self.url, headers=req_hdrs)
        html = urllib2.urlopen(req).read()
        match = self.ptn_sucuri.search(html)
        if match:
            jsstr = base64.b64decode( match.group(1) )
            jsstr = jsstr.replace(";document.cookie", ";cookie")
            jsstr = jsstr.replace("; location.reload();", "")
            self.cookie = js2py.eval_js(jsstr)
            # reload
            req_hdrs["Cookie"] = self.cookie
            req = urllib2.Request(self.url, headers=req_hdrs)
            html = urllib2.urlopen(req).read()
        self.imgurls = re.compile('data-src="(.*?)"').findall(html)

    @staticmethod
    def basename(url):
        return url.split('/')[-1].split('?')[0]


#===============================================================================
# ImageFile
#===============================================================================
class ImageFile(DAVNonCollection):
    """Represents an image file."""
    def __init__(self, path, environ, url, refurl, cookie):
        DAVNonCollection.__init__(self, path, environ)
        self.url = url
        self.refurl = refurl
        self.cookie = cookie

    def getContentLength(self):
        return None
    def getContentType(self):
        return util.guessMimeType(self.path)
    def getCreationDate(self):
        return None
    def getDisplayName(self):
        return self.name
    def getDisplayInfo(self):
        return {"type": "Image file"}
    def getEtag(self):
        return None
    def getLastModified(self):
        return None
    def supportRanges(self):
        return False

    def getContent(self):
        if self.cookie:
            req_hdrs["Cookie"] = cookie
        req = urllib2.Request(self.url, headers=req_hdrs)
        req.add_header('Referer', self.refurl)
        return urllib2.urlopen(req)

         
#===============================================================================
# DAVProvider
#===============================================================================
class MarumaruProvider(DAVProvider):
    def __init__(self):
        super(MarumaruProvider, self).__init__()

    def getResourceInst(self, path, environ):
        _logger.info("getResourceInst('%s')" % path)
        self._count_getResourceInst += 1
        root = RootCollection(environ)
        return root.resolve("", path)