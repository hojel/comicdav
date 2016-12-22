# -*- coding: utf-8 -*-
"""
Proxy hitomi.la as virtual DAV
"""
import urllib2
import re
from collections import OrderedDict
from wsgidav.util import joinUri
from wsgidav.dav_provider import DAVProvider, DAVNonCollection, DAVCollection
from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN, HTTP_INTERNAL_ERROR,\
    PRECONDITION_CODE_ProtectedProperty
from wsgidav import util

__docformat__ = "reStructuredText"

_logger = util.getModuleLogger(__name__)

from util import _dircache
_last_path = None

ROOT_URL = "http://hitomi.la"
FILE_URL = "http://%s.hitomi.la/galleries/%s/"

PTN_GALLERY = re.compile('<h1><a href=".*?(\d+)\.html">(.*?)</a></h1>')
PTN_IMAGE   = re.compile('"name":"(.*?)"')
PTN_GALID   = re.compile("(\d+)\.html")

#===============================================================================
# Browser
#===============================================================================
class RootCollection(DAVCollection):
    """Resolve top-level requests '/'."""
    
    def __init__(self, environ):
        DAVCollection.__init__(self, "/", environ)
        
    def getMemberNames(self):
        return ["by_date", "by_popularity", "by_artist", "by_tag", "by_language"]
    
    def getMember(self, name):
        # Handle visible categories and also /by_key/...
        path = joinUri(self.path, name)
        if name == "by_language":
            return LanguageCollection(path, self.environ)
        elif name == "by_date":
            return PageCollection(path, self.environ, "index-"+self.environ['hitomi.language'])
        elif name == "by_popularity":
            return PageCollection(path, self.environ, "popular-"+self.environ['hitomi.language'])
        elif name == "by_artist":
            return ArtistCollection(path, self.environ)
        elif name == "by_tag":
            return TagCollection(path, self.environ)
        return []


class LanguageCollection(DAVCollection):
    """Resolve '/by_language' URLs."""
    _languages = ["english", "japanese", "korean"]
    def __init__(self, path, environ):
        DAVCollection.__init__(self, path, environ)
    
    def getDisplayInfo(self):
        return {"type": "Languages"}
    
    def getMemberNames(self):
        return self._languages
    
    def getMember(self, name):
        if name in self._languages:
            ltype = "%s-%s" % ("index", name)
            return PageCollection(joinUri(self.path, name), self.environ, ltype)
        return []


class ArtistCollection(DAVCollection):
    """Resolve '/by_artist' URLs."""
    _artist = [ "cuvie",
                "fukudahda",
                "hazuki kaoru",
                "hisasi",
                "kirie masanobu",
                "kisaragi gunma",
                "sanbun kyoden",
                "shiwasu no okina",
                "takemura sesshu",
                "tosh",
                "tsukino jyogi",
                "yamatogawa",
                "yonekura kengo",
                "yuzuki n dash",
              ]
    def __init__(self, path, environ):
        DAVCollection.__init__(self, path, environ)
    
    def getDisplayInfo(self):
        return {"type": "Artist"}
    
    def getMemberNames(self):
        return self._artist
    
    def getMember(self, name):
        if name in self._artist:
            ltype = "artist/%s-%s" % (name, self.environ['hitomi.language'])
            return PageCollection(joinUri(self.path, name), self.environ, ltype)
        return []


class TagCollection(DAVCollection):
    """Resolve '/by_tag' URLs."""
    _tag = [ "female:ahegao",
             "female:cervix penetration",
             "female:defloration",
             "female:exhibitionism",
             "female:humiliation",
             "female:mind break",
             "female:mind control",
             "female:nakadashi",
             "female:parasite",
             "female:sole female",
             "female:tentacles",
             "female:x-ray",
             "story arc",
             "uncensored",
             "webtoon",
           ]
    def __init__(self, path, environ):
        DAVCollection.__init__(self, path, environ)
    
    def getDisplayInfo(self):
        return {"type": "Tag"}
    
    def getMemberNames(self):
        return self._tag
    
    def getMember(self, name):
        if name in self._tag:
            ltype = "tag/%s-%s" % (name, self.environ['hitomi.language'])
            return PageCollection(joinUri(self.path, name), self.environ, ltype)
        return []


class PageCollection(DAVCollection):
    """Resolve '/by_language/korean' URLs"""
    def __init__(self, path, environ, list_type):
        DAVCollection.__init__(self, path, environ)
        self.list_type = list_type
    
    def getDisplayInfo(self):
        return {"type": "Directory"}
    
    def getMemberNames(self):
        return map(str, range(1, 101))
    
    def getMember(self, name):
        if int(name) <= 100:
            url = ROOT_URL + "/%s-%s.html" % (self.list_type, name)
            return GListCollection(joinUri(self.path, name), self.environ, url)
        _logger.warning("expect number as page('%s')" % name)
        return []

#===============================================================================
# GListCollection
#===============================================================================
class GListCollection(DAVCollection):
    """Resolve '/by_language/korean/1' URLs"""
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.abspath = self.provider.sharePath + path
        try:
            self.galleries = _dircache[self.abspath]
        except KeyError:
            self.galleries = None
    
    def getDisplayInfo(self):
        return {"type": "List"}
    
    def getMemberNames(self):
        if self.galleries is None:
            self.extractInfo()
        return [self.name_clean(gname) for gid, gname in self.galleries]
    
    def getMember(self, name):
        if self.galleries is None:
            self.extractInfo()
        for gid, gname in self.galleries:
            if self.name_clean(gname) == name:
                url = ROOT_URL+"/galleries/%s.html" % gid
                return GalleryCollection(joinUri(self.path, name), self.environ, url)
        _logger.warning("unexpected name, %s" % name)
        return []

    def extractInfo(self):
        _logger.debug("GList('%s')" % self.url)
        html = urllib2.urlopen(self.url).read()
        self.galleries = PTN_GALLERY.findall(html)
        _dircache[self.abspath] = self.galleries

    def name_clean(self, name):
        return name.replace('|','')     # for ComicGlass


#===============================================================================
# GalleryCollection
#===============================================================================
class GalleryCollection(DAVCollection):
    """Resolve '/by_language/korean/1/title' URLs"""
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.abspath = self.provider.sharePath + path
        try:
            self.imgfiles = _dircache[self.abspath]
        except KeyError:
            self.imgfiles = None

    def getDisplayInfo(self):
        return {"type": "Gallery"}
    
    def getMemberNames(self):
        if self.imgfiles is None:
            self.extractInfo()
        return self.imgfiles.keys()

    def getMember(self, name):
        if self.imgfiles is None:
            self.extractInfo()
        return ImageFile(joinUri(self.path, name), self.environ, self.imgfiles[name], self.url)

    def extractInfo(self):
        # host
        gid = PTN_GALID.search(self.url).group(1)
        _logger.debug("gallery('%s')" % gid)
        #subdomain = chr(97+int(gid)%6)     # refer hitomi.la/download.js
        if self.environ['hitomi.language'] == 'korean': subdomain = 'ba'
        elif self.environ['hitomi.language'] == 'english': subdomain = 'la'
        else: subdomain = 'aa'
        baseurl = FILE_URL % (subdomain, gid)
        # img files
        nurl = self.url.replace('.html', '.js')
        jstr = urllib2.urlopen(nurl).read()
        self.imgfiles = PTN_IMAGE.findall(jstr)
        self.imgfiles = OrderedDict([(name, baseurl+name) for name in PTN_IMAGE.findall(jstr)])
        _dircache[self.abspath] = self.imgfiles


#===============================================================================
# ImageFile
#===============================================================================
class ImageFile(DAVNonCollection):
    """Represents an image file."""
    def __init__(self, path, environ, url, refurl):
        DAVNonCollection.__init__(self, path, environ)
        self.url = url
        self.refurl = refurl

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
        _logger.debug("image('%s') in page('%s')" % (self.url, self.refurl))
        req = urllib2.Request(self.url)
        req.add_header('Referer', self.refurl)
        return urllib2.urlopen(req)

         
#===============================================================================
# DAVProvider
#===============================================================================
class HitomiProvider(DAVProvider):
    def __init__(self, language='all'):
        super(HitomiProvider, self).__init__()
        self.language = language

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
        environ['hitomi.language'] = self.language
        root = RootCollection(environ)
        return root.resolve("", path)
