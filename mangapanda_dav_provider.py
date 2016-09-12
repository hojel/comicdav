# -*- coding: utf-8 -*-
"""
Proxy mangapanda.me as virtual DAV
"""
import urllib2
import re
from BeautifulSoup import BeautifulSoup
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

ROOT_URL = "http://www.mangapanda.com"

req_headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; U; CPU like Mac OS X; en) AppleWebKit/420+ (KHTML, like Gecko) Version/3.0 Mobile/1A543 Safari/419.3",
}

PTN_NAV = re.compile('"/popular/[^"]*/(\d+)"')
PTN_MAXPG  = re.compile("of (\d+)")
PTN_IMGURL = re.compile('<img[^>]*src="([^"]*)"')

AddImgExt = True

#===============================================================================
# Browising
#===============================================================================
class RootCollection(DAVCollection):
    """Resolve top-level requests '/'."""
    
    def __init__(self, environ):
        DAVCollection.__init__(self, "/", environ)
        
    def getMemberNames(self):
        return ["by_genre", ]
    
    def getMember(self, name):
        # Handle visible categories and also /by_key/...
        if name == "by_genre":
            return GenreCollection(joinUri(self.path, name), self.environ)
        _logger.error("unexpected member name, "+name)
        return None


class GenreCollection(DAVCollection):
    """ hardcoded without parsing site"""
    def __init__(self, path, environ):
        DAVCollection.__init__(self, path, environ)
        self.genres = [
          'Action', 'Adventure', 'Comedy', 'Demons', 'Drama',
          'Ecchi', 'Fantasy', 'Gender Bender', 'Harem', 'Historical',
          'Horror', 'Josei', 'Magic', 'Martial Arts', 'Mature',
          'Mecha', 'Military', 'Mystery', 'One Shot', 'Psychological',
          'Romance', 'School Life', 'Sci-Fi', 'Seinen', 'Shoujo',
          'Shoujoai', 'Shounen', 'Shounenai', 'Slice of Life', 'Smut',
          'Sports', 'Super Power', 'Supernatural', 'Tragedy', 'Vampire',
          'Yaoi', 'Yuri',
        ]
    
    def getDisplayInfo(self):
        return {"type": "Directory"}
    
    def getMemberNames(self):
        return self.genres
    
    def getMember(self, name):
        if name in self.genres:
            genre = name.lower().replace(' ','-')
            return DirectoryPageCollection(joinUri(self.path, name), self.environ, genre)
        _logger.error("unexpected member name, "+name)
        return None

#===============================================================================
# Directory w/ pages
#===============================================================================
class DirectoryPageCollection(DAVCollection):
    """ site: /popular/{genre}"""
    def __init__(self, path, environ, genre):
        DAVCollection.__init__(self, path, environ)
        self.genre = genre
        self.abspath = self.provider.sharePath + path
        try:
            self.maxidx = _dircache[self.abspath]
        except KeyError:
            self.maxidx = 0
    
    def getDisplayInfo(self):
        return {"type": "Pages"}
    
    def getMemberNames(self):
        if not self.maxidx:
            url = ROOT_URL + "/popular/%s" % self.genre
            _logger.debug(url)
            html = urllib2.urlopen(url).read()
            navurls = PTN_NAV.findall(html)
            _logger.debug("page buttons %d" % len(navurls))
            self.maxidx = int(navurls[-1])
            _dircache[self.abspath] = self.maxidx
        return map(str, range(0, self.maxidx+1, 30))
    
    def getMember(self, name):
        if name.isdigit():
            startid = int(name)
            url = ROOT_URL + "/popular/%s/%d" % (self.genre, startid)
            return DirectoryCollection(joinUri(self.path, name), self.environ, url)
        _logger.error("unexpected member name, "+name)
        return None


class DirectoryCollection(DAVCollection):
    """ site: /popular/{genre}/{startnum}"""
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.abspath = self.provider.sharePath + path
        try:
            self.mangas = _dircache[self.abspath]
        except KeyError:
            self.mangas = None
    
    def getDisplayInfo(self):
        return {"type": "List"}
    
    def getMemberNames(self):
        if self.mangas is None:
            self.extractInfo()
        return self.mangas.keys()
    
    def getMember(self, name):
        if self.mangas is None:
            self.extractInfo()
        try:
            url = ROOT_URL + "/" + self.mangas[name]
            return MangaCollection(joinUri(self.path, name), self.environ, url)
        except:
            return None

    def extractInfo(self):
        _logger.debug(self.url)
        html = urllib2.urlopen(self.url).read()
        soup = BeautifulSoup(html)
        self.mangas = OrderedDict()
        for node in soup.findAll('h3'):
            title = str(node.a.string)
            mid = node.a.get('href')[1:]
            self.mangas[title] = mid
        _dircache[self.abspath] = self.mangas


#===============================================================================
# Manga / Chapter
#===============================================================================
class MangaCollection(DAVCollection):
    """ site: /{manga}"""
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.abspath = self.provider.sharePath + path
        try:
            self.chapters = _dircache[self.abspath]
        except KeyError:
            self.chapters = None
    
    def getDisplayInfo(self):
        return {"type": "Manga"}
    
    def getMemberNames(self):
        if self.chapters is None:
            self.extractInfo()
        return self.chapters
    
    def getMember(self, name):
        if name.isdigit():
            url = self.url + "/" + name
            return ChapterCollection(joinUri(self.path, name), self.environ, url)
        _logger.error("unexpected chapter name, "+name)
        return None

    def extractInfo(self):
        _logger.debug(self.url)
        html = urllib2.urlopen(self.url).read()
        soup = BeautifulSoup(html)
        self.chapters = []
        for node in soup.find('table',{'id':'listing'}).findAll('a'):
            url = str(node.get('href'))
            self.chapters.append( url.split('/')[-1] )
        _dircache[self.abspath] = self.chapters


class ChapterCollection(DAVCollection):
    """ site: /{manga}/{chapter_num}"""
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
        self.abspath = self.provider.sharePath + path
        try:
            self.maxpg = _dircache[self.abspath]
        except KeyError:
            self.maxpg = 0
    
    def getDisplayInfo(self):
        return {"type": "Chapter"}
    
    def getMemberNames(self):
        if not self.maxpg:
            _logger.debug(self.url)
            html = urllib2.urlopen(self.url).read()
            soup = BeautifulSoup(html)
            node = soup.find('div',{'id':'selectpage'})
            if node is None:
                _logger.error("no page info found")
                return []
            maxpg_text = str(node)
            match = PTN_MAXPG.search(maxpg_text)
            if not match:
                _logger.error("no max page found")
                return []
            self.maxpg = int(match.group(1))
            _dircache[self.abspath] = self.maxpg
        if AddImgExt:
            return ["%d.jpg" % pg for pg in range(1, self.maxpg+1)]
        return map(str, range(1, self.maxpg+1))
    
    def getMember(self, name):
        url = self.url + "/" + name.rsplit(".", 1)[0]   # =splitext()
        return ImageFile(joinUri(self.path, name), self.environ, url)


#===============================================================================
# ImageFile
#===============================================================================
class ImageFile(DAVNonCollection):
    """ site: /{manga}/{chapter_num}/{page_num}"""
    def __init__(self, path, environ, url):
        DAVNonCollection.__init__(self, path, environ)
        self.url = url

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
        _logger.debug(self.url)
        html = urllib2.urlopen(self.url).read()
        match = PTN_IMGURL.search(html)
        if match:
            url = match.group(1)
            _logger.debug(url)
            req = urllib2.Request(url, headers=req_headers)
            return urllib2.urlopen(req)
        _logger.warning("no image found at "+self.url)
        return None

         
#===============================================================================
# DAVProvider
#===============================================================================
class MangapandaProvider(DAVProvider):
    def __init__(self):
        super(MangapandaProvider, self).__init__()

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
