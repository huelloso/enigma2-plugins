from twisted.web import resource, http, server

from enigma import eStreamServer, eServiceReference

import os.path

if os.path.isfile("/usr/lib/enigma2/python/Plugins/SystemPlugins/GstRtspServer/StreamServerControl.py"):
	from Plugins.SystemPlugins.GstRtspServer.StreamServerControl import streamServerControl
else:
	from Components.StreamServerControl import streamServerControl

from twisted.internet import reactor

import urllib

from Plugins.Extensions.StreamServerSeek.StreamServerSeek import StreamServerSeek

class StreamResource(resource.Resource):
	isLeaf = True
	validExt = ["ts", "trp", "avi", "divx", "f4v", "flv", "img", "ifo", "iso", "m2ts", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg", "mts", "vob", "wmv", "bdmv", "asf", "stream", "webm"]
	session = None
	_request = None

	def __init__(self, session):
		resource.Resource.__init__(self)
		self.session = session
		self.streamServerSeek = StreamServerSeek()

	def _onTemporaryLiveMode(self):
		if self.streamServerSeek._isTemporaryLiveMode and self.streamServerSeek._temporaryLiveModeService:
			print "[StreamserverSeek] Entered temporary Live-Mode - playing service"
			service = eServiceReference(self.streamServerSeek._temporaryLiveModeService)
			self.session.nav.playService(service)
			print "[StreamserverSeek] service %s" % service
			print "[StreamserverSeek] session.nav.getCurrentService() %s" % self.session.nav.getCurrentService()
			seek = self.session.nav.getCurrentService().seek()
			self.streamServerSeek._isTemporaryLiveModeActive = True

#		self._request.finish()
		reactor.callLater(1, self.finishRequest)
	
	def finishRequest(self):
		self._request.finish()

	def render(self, request):
		self._request = request

		request.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
		request.setHeader('Cache-Directive', 'no-cache');
		request.setHeader('Pragma-Directive', 'no-cache');
		request.setHeader('Pragma', 'no-cache');
		request.setHeader('Expires', '0');
		
		streamUrl = False
		length = len(request.postpath)
		if length > 0:
			if request.postpath[0] == 'rtsp':
				streamUrl = "rtsp://%s/stream" % request.getRequestHostname()
			elif request.postpath[0] == 'hls':
				streamUrl = "http://%s:8080/stream.m3u8" % request.getRequestHostname()
		
		if not streamUrl:
			request.setResponseCode(http.NOT_FOUND)
			return ""
		
		moviePath = ""
		movieNameWExt = ""
		i = 1
		while i < length:
			moviePath += "/%s" % request.postpath[i]
			movieNameWExt = request.postpath[i]
			i += 1
		
		if not os.path.isfile(moviePath):
			moviePath = moviePath.replace("+", " ")
			if i -1 < length:
				movieNameWExt = request.postpath[i-1].replace("+", " ")
			if not os.path.isfile(moviePath):
				request.setResponseCode(http.NOT_FOUND)
				return ""

		movieSplit = movieNameWExt.split(".")
		movieName = ""
		movieExt = ""
		i = 0
		while i < (len(movieSplit) -1):
			movieName += movieSplit[i]
			i += 1
		
		ext = movieSplit[-1]
		
		if (len(movieSplit) < 2) or (ext not in self.validExt):
			request.setResponseCode(http.FORBIDDEN)
			return ""

		if "min" in request.args:
			try:
				self.streamServerSeek._seekToMin = int(request.args["min"][0])
			except Exception:
				pass

		request.setHeader("Content-type", "")

		if ext == "ts":
			wait = False
			if self.streamServerSeek._isTemporaryLiveMode:
				print "[StreamserverSeek] Requested service does not require Live-Mode, but Live-Mode is still active. End it!"
				StreamServerSeek().endTemporaryLiveMode()
				wait = True
			elif streamServerControl.getInputMode() != eStreamServer.INPUT_MODE_BACKGROUND:
				print "[StreamserverSeek] Set input mode to BACKGROUND"
				StreamServerSeek().forceInputMode(eStreamServer.INPUT_MODE_BACKGROUND)
				wait = True
				
			result = streamServerControl.setEncoderService(eServiceReference("1:0:0:0:0:0:0:0:0:0:" + urllib.quote(moviePath)))
			if result == streamServerControl.ENCODER_SERVICE_SET or result == streamServerControl.ENCODER_SERVICE_ALREADY_ACTIVE:
				if not os.path.isfile("/usr/lib/enigma2/python/Plugins/SystemPlugins/GstRtspServer/StreamServerControl.py"):
					self.streamServerSeek.doSeek()

			request.setHeader("Location", streamUrl)
			request.setResponseCode(http.FOUND)

			if wait:
				reactor.callLater(1, self.finishRequest)
			else:
				request.finish()

			return server.NOT_DONE_YET
		
		from Screens.Standby import inStandby
		if inStandby is None:
			if self.streamServerSeek._isTemporaryLiveMode:
				print "[StreamserverSeek] Box already in temporary Live-Mode"
				request.setHeader("Location", streamUrl)
				request.setResponseCode(http.FOUND)
				return ""
			else:
				print "[StreamserverSeek] Requiring Live-Mode, but Box not in idle mode - do nothing"
				request.setResponseCode(http.INTERNAL_SERVER_ERROR)
				return ""
		else:
			streamServerControl.stopEncoderService()
			print "[StreamserverSeek] Switching on Box"
			self.streamServerSeek._temporaryLiveModeService = "4097:0:0:0:0:0:0:0:0:0:" + urllib.quote(moviePath)
			inStandby.onClose.append(self._onTemporaryLiveMode)
			print "%s" % StreamServerSeek
			print "%s" % StreamServerSeek()
			StreamServerSeek().changeIdleMode(False)
			self.streamServerSeek._isTemporaryLiveMode = True
			
			if streamServerControl.getInputMode() != eStreamServer.INPUT_MODE_LIVE:
				print "[StreamserverSeek] Set input mode to LIVE"
				StreamServerSeek().forceInputMode(eStreamServer.INPUT_MODE_LIVE)

			request.setHeader("Location", streamUrl)
			request.setResponseCode(http.FOUND)

			return server.NOT_DONE_YET
