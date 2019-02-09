import upnpclient,atexit,threading,socket
from urllib.parse import urlparse



cleanuplist = []
renewlist=[]


def cleanup():
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
						

#Asks them to open port from the outside world directly to us.
def addMapping(port,proto, desc="Description here"):
	devices = upnpclient.discover()
	for i in devices:
		l=urlparse(i.location).netloc
		if ":" in l:
			l = l.split(":")[0]

		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		s.connect((l, 12345))
		
		#Get the IP that we use to talk to that particular router
		ownAddr = s.getsockname()[0]
		print(ownAddr)
		s.close()
		del s
		
		for j in i.services:
			print(j.service_type)
			for k in j.actions:
				if k.name=="GetExternalIPAddress":
					if "WAN" in j.service_type:
						def clean():
							j.DeletePortMapping(
								NewRemoteHost="0.0.0.0",
								NewExternalPort=port,
								NewProtocol=proto,
							)
							print("del")
						
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
							print("add")
							
						renew()
						renewlist.append(renew)
						
def renewer():
	while 1:
		time.sleep(3600/2)
		try:
			for i in renewlist:
				i()
		except Exception as e:
			print(e)

				
rth = threading.Thread(target=renewer)
rth.daemon=True
addMapping(34531,"UDP")
print(getWANAddresses())
