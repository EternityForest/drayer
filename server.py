import drayer,time

if __name__ == '__main__':
	drayer.startServer()
	#drayer.startBittorent()
	drayer.startLocalDiscovery()
	#mappings = drayer.openRouterPort()
	d = drayer.DrayerStream("fooo.stream")
	#time.sleep(15)
	d.announceDHT()
	print(d.getAttr("PublicKey"))
	d["foo3"] = b"testing"
	d["foo"] = b"testing8"
	d["foo7"]=b"testing7"
	d["foo9"]=b"testing7"
	del d["foo7"]

	print(d["foo"])

	print(d["foo7"])
	while 1:
		pass
	
	
