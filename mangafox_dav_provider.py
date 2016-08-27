# -*- coding: utf-8 -*-
"""
Proxy mangafox.me as virtual DAV
"""
import urllib
import urllib2
import re
from BeautifulSoup import BeautifulSoup
from wsgidav.util import joinUri
from wsgidav.dav_provider import DAVProvider, DAVNonCollection, DAVCollection
from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN, HTTP_INTERNAL_ERROR,\
    PRECONDITION_CODE_ProtectedProperty
from wsgidav import util

__docformat__ = "reStructuredText"

_logger = util.getModuleLogger(__name__)

ROOT_URL = "http://mangafox.me"

PTN_MAXPG  = re.compile("of (\d+)")
PTN_IMGURL = re.compile('<img\s+src="([^"]*)"\s*onerror=')

ReverseChOrder = True
AddImgExt = True

#===============================================================================
# Browising
#===============================================================================
class RootCollection(DAVCollection):
    """Resolve top-level requests '/'."""
    
    def __init__(self, environ):
        DAVCollection.__init__(self, "/", environ)
        
    def getMemberNames(self):
        return ["by_genre", "by_alphabet", ]
    
    def getMember(self, name):
        # Handle visible categories and also /by_key/...
        if name == "by_alphabet":
            return AlphabetCollection(joinUri(self.path, name), self.environ)
        elif name == "by_genre":
            return GenreCollection(joinUri(self.path, name), self.environ)
        _logger.error("unexpected member name, "+name)
        return None


class AlphabetCollection(DAVCollection):
    def __init__(self, path, environ):
        DAVCollection.__init__(self, path, environ)
        self.items = ['#']
        self.items.append( map(chr, range(ord('A'), ord('Z')+1)) )
    
    def getDisplayInfo(self):
        return {"type": "Directory"}
    
    def getMemberNames(self):
        return self.items
    
    def getMember(self, name):
        if name in self.items:
            pname = '9' if name == '#' else name.lower()
            return DirectoryPageCollection(joinUri(self.path, name), self.environ, pname)
        _logger.error("unexpected member name, "+name)
        return None


class GenreCollection(DAVCollection):
    def __init__(self, path, environ):
        DAVCollection.__init__(self, path, environ)
        self.genres = [
          'Action', 'Adult', 'Adventure', 'Comedy', 'Doujinshi',
          'Drama', 'Ecchi', 'Fantasy', 'Gender Bender', 'Harem',
          'Historical', 'Horror', 'Josei', 'Martial Arts', 'Mature',
          'Mecha', 'Mystery', 'One Shot', 'Psychological', 'Romance',
          'School Life', 'Sci-fi', 'Seinen', 'Shoujo', 'Shoujo Ai',
          'Shounen', 'Shounen Ai', 'Slice of Life', 'Smut', 'Sports',
          'Supernatural', 'Tragedy', 'Webtoons', 'Yaoi', 'Yuri',
        ]
    
    def getDisplayInfo(self):
        return {"type": "Directory"}
    
    def getMemberNames(self):
        return self.genres
    
    def getMember(self, name):
        if name in self.genres:
            pname = name.lower().replace(' ','-')
            return DirectoryPageCollection(joinUri(self.path, name), self.environ, pname)
        _logger.error("unexpected member name, "+name)
        return None

#===============================================================================
# Directory w/ pages
#===============================================================================
class DirectoryPageCollection(DAVCollection):
    def __init__(self, path, environ, pname):
        DAVCollection.__init__(self, path, environ)
        self.pname = pname
    
    def getDisplayInfo(self):
        return {"type": "Pages"}
    
    def getMemberNames(self):
        url = ROOT_URL + "/directory/%s/" % self.pname
        _logger.debug(url)
        html = urllib2.urlopen(url).read()
        soup = BeautifulSoup(html)
        maxpg = 0
        for node in soup.find('div',{'id':'nav'}).findAll('a'):
            if node.text.isdigit():
                pg = int(node.text)
                if pg > maxpg: maxpg = pg
        return map(str, range(1, maxpg+1))
    
    def getMember(self, name):
        if name.isdigit():
            pg = int(name)
            url = ROOT_URL + "/directory/%s/%d.htm" % (self.pname, pg)
            return DirectoryCollection(joinUri(self.path, name), self.environ, url)
        _logger.error("unexpected member name, "+name)
        return None


class DirectoryCollection(DAVCollection):
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
    
    def getDisplayInfo(self):
        return {"type": "List"}
    
    def getMemberNames(self):
        _logger.debug(self.url)
        html = urllib2.urlopen(self.url).read()
        soup = BeautifulSoup(html)
        mangas = []
        for node in soup.find('ul',{'class':'list'}).findAll('li'):
            anode = node.find('a',{'class':'title'})
            title = anode.text
            url = anode.get('href')
            mid = url.rstrip('/').rsplit('/',1)[-1]
            _logger.debug(mid)
            mangas.append( str(mid) )
        return mangas
    
    def getMember(self, name):
        url = ROOT_URL+"/manga/"+name
        return MangaCollection(joinUri(self.path, name), self.environ, url)


#===============================================================================
# Manga / Chapter
#===============================================================================
class MangaCollection(DAVCollection):
    def __init__(self, path, environ, url):
        DAVCollection.__init__(self, path, environ)
        self.url = url
    
    def getDisplayInfo(self):
        return {"type": "Manga"}
    
    def getMemberNames(self):
        _logger.debug(self.url)
        html = urllib2.urlopen(self.url).read()
        soup = BeautifulSoup(html)
        chapters = []
        for node in soup.find('div',{'id':'chapters'}).findAll('a',{'class':'tips'}):
            title = str(node.text)
            url = node.get('href')
            if url.startswith(self.url):
                url = url[len(self.url)+1: ]
            chid = url.rsplit('/', 1)[0].replace('/', '_')
            _logger.debug(chid)
            chapters.append( str(chid) )
        if ReverseChOrder:
            chapters.reverse()
        return chapters
    
    def getMember(self, name):
        url = self.url + "/%s/" % name.replace('_', '/') 
        return ChapterCollection(joinUri(self.path, name), self.environ, url)


class ChapterCollection(DAVCollection):
    def __init__(self, path, environ, baseurl):
        DAVCollection.__init__(self, path, environ)
        self.baseurl = baseurl
    
    def getDisplayInfo(self):
        return {"type": "Chapter"}
    
    def getMemberNames(self):
        url = self.baseurl + "1.html"
        _logger.debug(url)
        html = urllib2.urlopen(url).read()
        soup = BeautifulSoup(html)
        node = soup.find('select',{'class':'m'})
        if node is None:
            _logger.error("no page info found")
            return []
        maxpg_text = str(node.parent)
        match = PTN_MAXPG.search(maxpg_text)
        if not match:
            _logger.error("no max page found")
            return []
        maxpg = int(match.group(1))
        if AddImgExt:
            return ["%d.jpg" % pg for pg in range(1, maxpg+1)]
        return map(str, range(1, maxpg+1))
    
    def getMember(self, name):
        url = self.baseurl + "%s.html" % name.rsplit('.', 1)[0]  # =splitext
        return ImageFile(joinUri(self.path, name), self.environ, url)


#===============================================================================
# ImageFile
#===============================================================================
class ImageFile(DAVNonCollection):
    """Represents an image file."""
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
            return urllib2.urlopen(url)
        _logger.warning("no image found at "+self.url)
        return None

         
#===============================================================================
# Provider
#===============================================================================
class MangafoxProvider(DAVProvider):
    """
    DAV provider that serves a VirtualResource derived structure.
    """
    def __init__(self):
        super(MangafoxProvider, self).__init__()

    def getResourceInst(self, path, environ):
        """Return path.
        
        See DAVProvider.getResourceInst()
        """
        _logger.info("getResourceInst('%s')" % path)
        self._count_getResourceInst += 1
        root = RootCollection(environ)
        return root.resolve("", path)
