import drayer

if __name__ == '__main__':
	drayer.startServer()
	#drayer.startBittorent()
	drayer.startLocalDiscovery()
	#mappings = drayer.openRouterPort()
	d = drayer.DrayerStream("fooo.stream")
	d.advertiseOnBittorent()
	print(d.getAttr("PublicKey"))
	d["foo3"] = b"testing"
	d["foo"] = b"testing3"
	print(d["foo"])
	
	while 1:
		pass
	
	
