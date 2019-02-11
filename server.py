import drayer,time

if __name__ == '__main__':
	drayer.startServer()
	#drayer.startBittorent()
	drayer.startLocalDiscovery()
	#mappings = drayer.openRouterPort()
	d = drayer.DrayerStream("fooo.stream","H3E55+t/tItsDp/TB053Jr9ppL2WPycRIdp5Gndrzfs=")

	#time.sleep(15)
	#d.announceDHT()
	print(d.getAttr("PublicKey"))
	d["foo3"] = b"testing"
	d["foo"] = b"testing8"
	d["foo7"]=b"testing7"
	d["foo6"]=b"testing7"
	
	#d["__drayer_siblings"] = msgp{
	#del d["foo7"]

	print(d["foo"])

	while 1:
		pass
	
	
