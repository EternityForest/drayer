import drayer

if __name__ == '__main__':
	drayer.startServer()
	d = drayer.DrayerStream("fooo.stream")
	print(d.getAttr("PublicKey"))
	d["foo3"] = b"testing"
	d["foo"] = b"testing3"
	print(d["foo"])
	
	
