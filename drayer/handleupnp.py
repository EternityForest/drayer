import upnpclient,atexit,threading,socket,time
from urllib.parse import urlparse


listlock = threading.Lock()

cleanuplist = []
renewlist=[]


def cleanup():
	with listlock:
		for i in cleanuplist:
			try:
				i()
			except Exception as e:
				print(e)
atexit.register(cleanup)


#Ask routers for our external IPs
def getWANAddresses():
	devices = upnpclient.discover()
	addresses = []
	
	for i in devices:
		for j in i.services:
			for k in j.actions:
				if k.name=="GetExternalIPAddress":
					if "WAN" in j.service_type:
						addresses.append(j.GetExternalIPAddress()["NewExternalIPAddress"])
	return addresses
						


class Mapping():
	"Represents one port mapping"
	
	def __init__(self, clfun, renfun):
		self.clfun = clfun
		self.renfun = renfun
	
	def __del__(self):
		self.delete()
	
	def delete(self):
		self.clfun()
		
		with listlock:
			if self.clfun in cleanuplist:
				cleanuplist.remove(self.clfun)
			if self.renfun in cleanuplist:
				renewlist.remove(self.clfun)
		
				
#Asks them to open port from the outside world directly to us.
def addMapping(port,proto, desc="Description here"):
	"""Returns a list of Mapping objects"""
	devices = upnpclient.discover()
	mappings = []

	for i in devices:
		l=urlparse(i.location).netloc
		if ":" in l:
			l = l.split(":")[0]

		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		s.connect((l, 12345))
		
		#Get the IP that we use to talk to that particular router
		ownAddr = s.getsockname()[0]
		s.close()
		del s
		
		for j in i.services:
			for k in j.actions:
				if k.name=="GetExternalIPAddress":
					if "WAN" in j.service_type:
						def clean():
							j.DeletePortMapping(
								NewRemoteHost="0.0.0.0",
								NewExternalPort=port,
								NewProtocol=proto,
							)
							
						with listlock:
							cleanuplist.append(clean)
							
						def renew(): 
							j.AddPortMapping(
								NewRemoteHost='0.0.0.0',
								NewExternalPort=port,
								NewProtocol=proto,
								NewInternalPort=port,
								NewInternalClient=ownAddr,
								NewEnabled='1',
								NewPortMappingDescription=desc,
								NewLeaseDuration=3600
							)
							
						renew()
						with listlock:
							renewlist.append(renew)
						mappings.append(Mapping(clean,renew))
	return mappings
						
def renewer():
	while 1:
		time.sleep(3600/2)
		try:
			with listlock:
				for i in renewlist:
					i()
		except Exception as e:
			print(e)

				
rth = threading.Thread(target=renewer)
rth.daemon=True
rth.start()