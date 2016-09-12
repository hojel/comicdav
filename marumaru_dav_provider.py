# -*- coding: utf-8 -*-
"""
Proxy marumaru.in as virtual DAV
"""
import urllib
import urllib2
from BeautifulSoup import BeautifulSoup
from collections import OrderedDict
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

from util import _dircache
_last_path = None

ROOT_URL = "http://marumaru.in"

req_hdrs = {
    "User-Agent":"Mozilla/5.0 (iPad; CPU OS 7_0 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Version/7.0 Mobile/11A465 Safari/9537.53",
    "Cookie":"",
}

PTN_MAXPG   = re.compile('<a href="[^"]*p=(\d+)[^"]*"[^>]*> *<img src="[^"]*/lp.gif"')
PTN_SRURL   = re.compile("goHref\('(.*?)'\)")
PTN_ARCHIVE = re.compile("/archives/")
PTN_IMGURL  = re.compile('data-src="(.*?)"')
PTN_SUCURI  = re.compile("S\s*=\s*'([^']*)'")

#===============================================================================
# Virtual Collection
#===============================================================================
class RootCollection(DAVCollection):
    """Resolve top-level requests '/'."""
    def __init__(self, environ):
        DAVCollection.__init__(self, "/", environ)
        
    def getMemberNames(self):
        return ["by_board", "by_genre", ]
    
    def getMember(self, name):
        # Handle visible categories and also /by_key/...
        if name == "by_board":
            return BoardCollection(joinUri(self.path, name), self.environ)
        elif name == "by_genre":
            return GenreCollection(joinUri(self.path, name), self.environ)
        _logger.error("unexpected member name, "+name)
        return None

#===============================================================================
# Board
#===============================================================================
class BoardCollection(DAVCollection):
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
    
    def __init__(self, path, environ):
        DAVCollection.__init__(self, path, environ)
        
    def getMemberNames(self):
        return [tname for tname,_ in self.btable]
    
    def getMember(self, name):
        for tname, tid in self.btable:
            if tname == name:
                url = ROOT_URL + "/?c=1/%d" % tid
                url += "&sort=gid"
                return ListPageCollection(joinUri(self.path, name), self.environ, url)
        _logger.error("unexpected member name, "+name)
        return None


#===============================================================================
# Genre
#===============================================================================
class GenreCollection(DAVCollection):
    """Resolve top-level requests '/'."""
    genres = ["17", "SF", "TS", "개그", "드라마",
              "러브코미디", "먹방", "백합", "붕탁", "순정",
              "스릴러", "스포츠", "시대", "액션", "일상+치유",
              "추리", "판타지", "학원", "호러"
             ]
    
    def __init__(self, path, environ):
        DAVCollection.__init__(self, path, environ)
        
    def getMemberNames(self):
        return self.genres
    
    def getMember(self, name):
        url = ROOT_URL + "/?r=home&m=bbs&bid=manga&where=tag&keyword=G%3A"+name.replace("+", "%2B") 
        url += "&sort=gid"
        return ListPageCollection(joinUri(self.path, name), self.environ, url)


#===============================================================================
# List w/ pages
#===============================================================================
class ListPageCollection(DAVCollection):
    """ site: /?c=1/{id}"""
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.abspath = self.provider.sharePath + path
        try:
            self.maxpage = _dircache[self.abspath]
        except KeyError:
            self.maxpage = 0
    
    def getDisplayInfo(self):
        return {"type": "Pages"}
    
    def getMemberNames(self):
        if not self.maxpage:
            self.extractInfo()
        return map(str, range(1, self.maxpage+1))
    
    def getMember(self, name):
        if name.isdigit():
            url = self.url + "&p=%s" % name
            return ListCollection(joinUri(self.path, name), self.environ, url)
        _logger.error("unexpected member name, "+name)
        return None

    def extractInfo(self):
        _logger.debug(self.url)
        req = urllib2.Request(self.url, headers=req_hdrs)
        html = urllib2.urlopen(req).read()
        match = PTN_MAXPG.search(html)
        if match:
            self.maxpage = int(match.group(1))
            _dircache[self.abspath] = self.maxpage

class ListCollection(DAVCollection):
    """ site: /?c=1/{id}&p={num}"""
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.abspath = self.provider.sharePath + path
        try:
            self.series = _dircache[self.abspath]
        except KeyError:
            self.series = None
    
    def getDisplayInfo(self):
        return {"type": "List"}
    
    def getMemberNames(self):
        if self.series is None:
            self.extractInfo()
        return self.series.keys()
    
    def getMember(self, name):
        if self.series is None:
            self.extractInfo()
        try:
            return SeriesCollection(joinUri(self.path, name), self.environ, self.series[name])
        except:
            return None

    def extractInfo(self):
        _logger.debug(self.url)
        req = urllib2.Request(self.url, headers=req_hdrs)
        html = urllib2.urlopen(req).read()
        soup = BeautifulSoup(html)
        self.series = OrderedDict()
        for node in soup.findAll('div', {'class':'list'}):
            title = str(node.find('span', {'class':'subject'}).string)
            url = ROOT_URL + PTN_SRURL.search(node['onclick']).group(1)
            self.series[title] = url
        _dircache[self.abspath] = self.series


#===============================================================================
# SeriesCollection/EpisodeCollection
#===============================================================================
class SeriesCollection(DAVCollection):
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.abspath = self.provider.sharePath + path
        try:
            self.episodes = _dircache[self.abspath]
        except KeyError:
            self.episodes = None
    
    def getDisplayInfo(self):
        return {"type": "Series"}
    
    def getMemberNames(self):
        if self.episodes is None:
            self.extractInfo()
        return self.episodes.keys()
    
    def getMember(self, name):
        if self.episodes is None:
            self.extractInfo()
        try:
            return EpisodeCollection(joinUri(self.path, name), self.environ, self.episodes[name])
        except:
            return None

    def extractInfo(self):
        _logger.debug(self.url)
        req = urllib2.Request(self.url, headers=req_hdrs)
        html = urllib2.urlopen(req).read()
        soup = BeautifulSoup(html)
        self.episodes = OrderedDict()
        for node in soup.findAll('a', {'href':PTN_ARCHIVE}):
            #title = str(node.string)
            title = unicode(node.text).encode('utf-8')
            url = node.get('href')
            self.episodes[title] = url
        _dircache[self.abspath] = self.episodes


class EpisodeCollection(DAVCollection):
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.abspath = self.provider.sharePath + path
        try:
            self.cookie, self.imgurls = _dircache[self.abspath]
        except KeyError:
            self.cookie = None
            self.imgurls = None
    
    def getDisplayInfo(self):
        return {"type": "Episode"}
    
    def getMemberNames(self):
        if self.imgurls is None:
            self.extractInfo()
        #return [self.basename(url) for url in self.imgurls]
        return ["%s.jpg" % cnt for cnt in range(1, len(self.imgurls)+1)]
    
    def getMember(self, name):
        if self.imgurls is None:
            self.extractInfo()
        """ basename as image file name
        for url in self.imgurls:
            fname = self.basename(url)
            if fname == name:
                return ImageFile(joinUri(self.path, name), self.environ, url, self.url, self.cookie)
        return None
        """
        """ counter as image file name """
        idx = int(name.split('.')[0]) - 1
        url = self.imgurls[idx]
        return ImageFile(joinUri(self.path, name), self.environ, url, self.url, self.cookie)

    def extractInfo(self):
        url = self.url
        url = url.replace("http://www.shencomics.com", "http://www.yuncomics.com")
        url = url.replace("http://blog.yuncomics.com", "http://www.yuncomics.com")
        _logger.debug(url)
        req = urllib2.Request(url, headers=req_hdrs)
        html = urllib2.urlopen(req).read()
        match = PTN_SUCURI.search(html)
        if match:
            jsstr = base64.b64decode( match.group(1) )
            jsstr = jsstr.replace(";document.cookie", ";cookie")
            jsstr = jsstr.replace("; location.reload();", "")
            self.cookie = js2py.eval_js(jsstr)
            # reload
            req_hdrs["Cookie"] = self.cookie
            req = urllib2.Request(self.url, headers=req_hdrs)
            html = urllib2.urlopen(req).read()
        self.imgurls = PTN_IMGURL.findall(html)
        _dircache[self.abspath] = (self.cookie, self.imgurls)

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
            req_hdrs["Cookie"] = self.cookie
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
        global _last_path
        npath = self.sharePath + path
        if _last_path == npath:
            global _dircache
            #del _dircache[npath]
            _dircache.__delete__(npath)
        _last_path = npath
        root = RootCollection(environ)
        return root.resolve("", path)
