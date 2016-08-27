# -*- coding: utf-8 -*-
"""
Proxy hitomi.la as virtual DAV
"""
import urllib2
import re
from wsgidav.util import joinUri
from wsgidav.dav_provider import DAVProvider, DAVNonCollection, DAVCollection
from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN, HTTP_INTERNAL_ERROR,\
    PRECONDITION_CODE_ProtectedProperty
from wsgidav import util

__docformat__ = "reStructuredText"

_logger = util.getModuleLogger(__name__)

ROOT_URL = "https://hitomi.la"
FILE_URL = "https://i.hitomi.la/galleries/"

PTN_GALLERY = re.compile('<h1><a href=".*?(\d+)\.html">(.*?)</a></h1>')
PTN_IMAGE   = re.compile('"name":"(.*?)"')
PTN_GALID   = re.compile("(\d+)\.html")

#===============================================================================
# Virtual Collection
#===============================================================================
class RootCollection(DAVCollection):
    """Resolve top-level requests '/'."""
    
    def __init__(self, environ):
        DAVCollection.__init__(self, "/", environ)
        
    def getMemberNames(self):
        return ["by_language"]
    
    def getMember(self, name):
        # Handle visible categories and also /by_key/...
        if name == "by_language":
            return LanguageCollection(joinUri(self.path, name), self.environ)
        return None


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
            return PageCollection(joinUri(self.path, name), self.environ, "index")
        return None


class PageCollection(DAVCollection):
    """Resolve '/by_language/korean' URLs"""
    def __init__(self, path, environ, list_type):
        DAVCollection.__init__(self, path, environ)
        self.list_type = list_type
    
    def getDisplayInfo(self):
        return {"type": "List"}
    
    def getMemberNames(self):
        return map(str, range(1, 101))
    
    def getMember(self, name):
        if int(name) <= 100:
            return GListCollection(joinUri(self.path, name), self.environ, self.list_type)
        _logger.error("expect number as page('%s')" % name)
        return None

#===============================================================================
# GListCollection
#===============================================================================
class GListCollection(DAVCollection):
    """Resolve '/by_language/korean/1' URLs"""
    def __init__(self, path, environ, list_type):
        DAVCollection.__init__(self, path, environ)
        sp = self.path.rsplit('/', 2)
        self.url = ROOT_URL + "/%s-%s-%s.html" % (list_type, sp[-2], sp[-1])
        self.galleries = None
    
    def getDisplayInfo(self):
        return {"type": "Page"}
    
    def getMemberNames(self):
        if self.galleries is None:
            _logger.debug("GList('%s')" % self.url)
            html = urllib2.urlopen(self.url).read()
            self.galleries = PTN_GALLERY.findall(html)
        return ["%s___%s" % (gname, gid) for gid, gname in self.galleries]
    
    def getMember(self, name):
        if not '___' in name:
            _logger.error("unexpected name in GList('%s')" % name)
            return None
        gid = name.rsplit('___', 1)[-1]
        url = ROOT_URL+"/galleries/%s.html" % gid
        return GalleryCollection(joinUri(self.path, name), self.environ, url)


#===============================================================================
# GalleryCollection
#===============================================================================
class GalleryCollection(DAVCollection):
    """a collection of images."""

    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.imgnames = None

    def getDisplayInfo(self):
        return {"type": "Gallery"}
    
    def getMemberNames(self):
        if self.imgnames is None:
            nurl = self.url.replace(".html", ".js")
            _logger.debug("gallery('%s')" % nurl)
            jstr = urllib2.urlopen(nurl).read()
            self.imgnames = PTN_IMAGE.findall(jstr)
        return self.imgnames

    def getMember(self, name):
        return ImageFile(joinUri(self.path, name), self.environ, self.url)


#===============================================================================
# ImageFile
#===============================================================================
class ImageFile(DAVNonCollection):
    """Represents an image file."""
    def __init__(self, path, environ, url):
        DAVNonCollection.__init__(self, path, environ)
        self.gallery = PTN_GALID.search(url).group(1)
        self.refurl = url

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
        url = FILE_URL + self.gallery + "/" + self.name
        _logger.debug("image('%s') in page('%s')" % (url, self.refurl))
        req = urllib2.Request(url)
        req.add_header('Referer', self.refurl)
        return urllib2.urlopen(req)

         
#===============================================================================
# HitomiProvider
#===============================================================================
class HitomiProvider(DAVProvider):
    """
    DAV provider that serves a VirtualResource derived structure.
    """
    def __init__(self):
        super(HitomiProvider, self).__init__()

    def getResourceInst(self, path, environ):
        """Return _Hitomi object for path.
        
        path is expected to be 
            categoryType/category/name/artifact
        for example:
            'by_tag/cool/My doc 2/info.html'

        See DAVProvider.getResourceInst()
        """
        _logger.info("getResourceInst('%s')" % path)
        self._count_getResourceInst += 1
        root = RootCollection(environ)
        return root.resolve("", path)