
import libnacl,os,sqlite3,struct,time,weakref,msgpack,requests, socket,threading,select,urllib,random

from base64 import b64decode, b64encode

import cherrypy

http_port = 33125

MCAST_GRP = '224.7.130.8'
MCAST_PORT = 15723


listensock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
listensock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listensock.bind(("", MCAST_PORT))
mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)

listensock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
listensock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  

MULTICAST_TTL = 2
sendsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sendsock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)

sendsock.bind(("",0))



class DrayerWebServer(object):
	@cherrypy.expose
	def index(self):
		return "Hello World!"
        
	@cherrypy.expose
	def newRecords(self, streampk, t):
		"Returns a msgpacked list of new records"
		cherrypy.response.headers['Content-Type']="application/octet-stream"
		t = int(t)
		c = _allStreams[b64decode(streampk)].getThreadCopy().getRecordsSince(t)
		limit = 100
		l = []
		for i in c:
			if limit<1:
				break
			l.append({
				"hash":i["hash"],
				"key":i["key"],
				"val":i["value"],
				"id": i["id"],
				"sig":i["signature"],
				"prev":i["prev"],
				"prevch":i["prevchange"],
				"mod":i["modified"],
				"chain":i["chain"]
			})
	
		x= msgpack.packb(l)
		return(x)
			
		
		
		
cherrypy.config.update({'server.socket_port': http_port,'server.socket_host' : '0.0.0.0',
})

_allStreams = weakref.WeakValueDictionary()




class DrayerStream():
	def __init__(self, fn=None, pubkey=None,noServe=False):
		
		if pubkey:
			if isinstance(pubkey, str):
				pubkey=b64decode(pubkey)
		
		self.pubkey = None
		self.fn = fn
		
		self.noServe = noServe
	
		if fn:
			self.conn=sqlite3.connect(fn)
			self.conn.row_factory = sqlite3.Row
			
			c=self.conn.cursor()
			#This is just a basic key value table for really simple basic info about the
			#Stream
			c.execute("CREATE TABLE IF NOT EXISTS attr (key text, value text);")
			
			#This is the actual record chain
			## id: Numeric incrementing ID
			##key, value: same meaning as any other dict
			##hash: the hash of the value(blake2b). The signature is overthe hash
				#	not the real data, so that we can implement partial
				#   mirrors with all metadata but without large files 
			#modified: Modification date, microsecods since unix
			#prev: Pointer to the previous block in the chain. Points to the ID.
			#prevchange: At the time this block was last changed, it points to the previous most recent modified date
			#chain: If empty, it's the default chain. But we can also store "sibling chains" in here. We
			#would list them by the public key.
			 
			c.execute("CREATE TABLE IF NOT EXISTS record (id integer primary key, key text, value blob, hash blob, modified integer, prev integer, prevchange integer, signature blob, chain blob);")

			pk = self.getAttr("PublicKey")
			if pk:
				pk = b64decode(pk)
			if pubkey and pk and not(pk==pubkey):
					raise ValueError("You specified a pubkey, but the file already contains one that does not match")
					
			if pk:
				self.pubkey = pk
			else:
				if not pubkey:
					#No pubkey in the file or in the input, assume they want to make a new
					vk, sk = libnacl.crypto_sign_keypair()
					self.setAttr("PublicKey", b64encode(vk).decode("utf8"))
					self.pubkey = vk
					self.privkey = sk
					self.savePK()
				else:
					#Get the pubkey from user
					self.setAttr("PublicKey", b64encode(pubkey).decode("utf8"))
					self.pubkey = pubkey
					self.privkey = None
				
			if os.path.exists(fn+".privatekey"):
				with open(fn+".privatekey") as f:
					self.privkey = b64decode(f.read())
					
			if noServe==False:
				_allStreams[self.pubkey] = self
	
	
	def getThreadCopy(self):
		"Returns another DrayerStream that should be open to the same db"
		return DrayerStream(self.fn,self.pubkey,True if self.noServe else "copy")
	
	
	def getBytesForSignature(self, id,key,h, modified, prev,prevchanged):
		#This is currently the definition of how to make a signature
		return struct.pack("<QqqqL", id,modified,prev, prevchanged,len(key))+key.encode("utf8")+h
	
	def makeSignature(self, id,key, h, modified, prev,prevchanged,chain=None):
		d = self.getBytesForSignature(id,key,h, modified, prev,prevchanged)
		return libnacl.crypto_sign_detached(d, chain or self.privkey)
		
		
	
	def sync(self,url=None):
		"""Syncs with a remote server"""
		if url:
			if url.startswith("http"):
				self.httpSync(url)
		
		
		if torrentServer:
			bthash=libnacl.crypto_generichash(self.pubkey)
			bthash=libnacl.crypto_generichash(bthash)[:20]			
			#Sync with 5 random DHT nodes. We just hope that eventually we will
			#get good data.
			print("searching",bthash)
			x = torrentServer.get_peers(bthash)
			print(x)
			if x:
				for i in random.shuffle()[:5]:
					print("Found BitTorrent node!",i)
					try:
						self.directHttpSync(ip,port)
					except:
						print(traceback.format_exc())
					
				
			
		if localDiscovery:
			print("doing local discovery")
			sendsock.sendto(("getRecordsSince\n"+b64encode(self.pubkey).decode("utf8")+"\n"+str(self.getModifiedTip())).encode("utf8"), (MCAST_GRP, MCAST_PORT))
	
	def directHttpSync(self,ip,port):
		"Use an ip port pair to sync"
		self.httpSync("http://"+ip+":"+str(port))

	def httpSync(self,url):
		"""Gets any updates that an HTTP server might have"""
		if url.endswith("/"):
			pass
		else:
			url+="/"
			
		#newRecords/PUBKEY/sinceTime
		r = requests.get(
				url+
				"newRecords/"+
				urllib.parse.quote_plus(b64encode(self.pubkey).decode("utf8"))+
				"/"+str(self.getModifiedTip()
			),stream=True)
		r.raise_for_status()
		r=r.raw.read(100*1000*1000)
		
		r = msgpack.unpackb(r)
		
		#Haven't needed to read siblings yet
		siblings = None
		
		
		for i in r:
			if i[b'chain']:
				if not siblings:
					siblings=self.getSiblingChains()
					
			self.insertRecord(i[b"id"],i[b"key"].decode("utf8"),i[b"val"], i[b"mod"], i[b"prev"], i[b"prevch"],i[b"sig"],i[b'chain'])
			
			
	def checkSignature(self, id,key,h, modified, prev,prevchanged, sig,chain=None):
		d = self.getBytesForSignature(id,key,h, modified, prev,prevchanged)
		return libnacl.crypto_sign_verify_detached(sig, d, chain or self.pubkey)
		
	def getSiblingChains():
		"""Return a dict of all sibling chains, including ones referenced BY sibling chains that have not been synced yet.
			dict entries returned as:
			
			pubkey(bin): entrytimestamp, validstart(0 for never), validend(0 for none)
					
			Nodes merge in records from other nodes,and later entrytimestamps take priority.
			We have no way to really delete these records, just to leave an invalid marker.
			
			However, we have a special reseved entry. A pubkey value of b"COMPLETE" declares
			that there are no period entries older than that which are still valid.
			
			To make things easier, only one period per key.
			
			The actual DrayerSiblings record format is just a list of msgpack dicts.
		"""	
		
		c=self.conn.cursor()
		
		#Note that we read from all siblings. The sibling of our sibling is also our sibling.
		c.execute('SELECT id FROM record WHERE key="__drayer_siblings__"',(key,))
		periods = {}
		
		#This is a really slow process of reading things. We probably need to cache this somehow.
		for i in c:
			self.validateRecord(i["id"], i["chain"])
			#Get all the records
			value = msgpack.unpackb(i["value"])
			for j in value:
				if j["pubkey"] in periods:
					if j["timestamp"] > periods[j["pubkey"]]["timestamp"]:
							periods[j["pubkey"]] = j
				else:
					periods[i["pubkey"]] = j
			torm=[]
		
		#After we have everything, delete the 
		#Records that have been deleted by COMPLETEs.
		for j in periods:
			if periods[j]["pubkey"]== b'COMPLETE':
				for k in periods:
					if periods[k]["timestamp"]< periods["j"]["timestamp"]:
						torm.append(k)
		for i in torm:
			del periods[i]
			
		#TODO: Actually delete the unneeded stuff, and merge all the siblings into one
		#which we then write back to the main chain
		
		
		return {i:(periods[i]["timestamp"], periods[i]["from"],periods[i]["to"]) for i in periods}
						
			
	def validateRecord(self,id, chain=b""):
		##Make sure a record is actually supposed to be there
		x = self.getRecordById(id,chain)
		
		h= libnacl.crypto_generichash(x["value"])
		if not h==x["hash"]:
			raise RuntimeError("Bad Hash")
		

		self.checkSignature(id,x["key"], h,x["modified"], x["prev"],x["prevchange"], x["signature"],chain)
		if self.hasRecordBeenDeleted(id,chain):
			raise RuntimeError("Record appears valid but was deleted by a later change")

		
		
		
	def insertRecord(self, id,key,value, modified, prev,prevchanged, signature, chain=b""):
		#Most basic test, make sure it's signed correctly
		
		#We don't supply a hash because we check it here anyway
		h= libnacl.crypto_generichash(value)
		self.checkSignature(id,key, h,modified, prev,prevchanged, signature,chain)
	
		#The thing that the old block that we might be replacing used to point at
		oldPrev = self.getPrev(id,chain)
		

		mtip = self.getModifiedTip(chain)
		if not prevchanged == mtip:
			#Obviously we have to allow anything at all to connect on to the very beginning.
			if mtip:
				#And of course we have the exception for linking to the back
				if self.getChainBackPointer(chain)==id:
					raise ValueError("New records must connect to the previous modified value")
		
		tip = self.getChainTip(chain)
		
		if not prev ==tip:
			if not self.getRecordById(id,chain):
				#Tip is 0, we can start anywhere
				if tip:
					#Also, we can append to the back
					if self.getChainBackPointer(chain)==id:
						raise ValueError("New records must modify an existing entry, or append to one of the ends")
				
				
		with self.conn:
			self.conn.execute("DELETE FROM record WHERE id=? AND chain=?",(id,chain))
			self.conn.execute("INSERT INTO record VALUES(?,?,?,?,?,?,?,?,?)",(id,key,value,h,modified,prev,prevchanged, signature,chain))
			#Check if this comm
			if oldPrev:
				if not oldPrev==prev:
					#If we changed prev we need to garbage collect the unreachable node.
					hasRecordBeenDeleted(oldPrev,chain)
					
	def __setitem__(self,k, v):
		k,v=self.filterInsert(k,v)
		
		id = self.getIdForKey(k)
		
		if not id:
			id= self.getChainTip()+1
			prev = self.getChainTip()
		else:
			prev= self.getPrev(id)
			
		mtime = int(time.time()*1000*1000)
		prevMtime = self.getModifiedTip()
		h = libnacl.crypto_generichash(v)
		sig = self.makeSignature(id,k,h,mtime,prev,prevMtime)
		self.insertRecord(id,k,v,mtime,prev,prevMtime,sig)
		self.broadcastUpdate()
		
	def __getitem__(self,k):
		id = self.getIdForKey(k)
		if id==None:
			raise KeyError(k)
		
		id,key,value,h,mtime,prev,prevmtime,sig,chain= self.getRecordById(id)
		self.validateRecord(id,chain)
		
		return self.filterGet(value)
		
		
	
	def filterInsert(self,k,v):
		"Preprocess values inserted with the dict insert style"
		return k,v
	
	def filterGet(self,v):
		return v
		
	def advertiseOnBittorent(self):
		if self.noServe:
			raise RuntimeError("noServe is enabled for this object. Perhaps you meant to advertise from the main thread?")
			
		bthash=libnacl.crypto_generichash(self.pubkey)
		bthash=libnacl.crypto_generichash(bthash)[:20]
		
		if torrentServer:
			print("advertizing", bthash)
			torrentServer.announce_peer(bthash, http_port,0,False)
			
		
	def getIdForKey(self, key):
		"Returns the ID of the most recent record with a given key"
		c=self.conn.cursor()
		c.execute("SELECT id FROM record WHERE key=? ORDER BY modified desc",(key,))
		x = c.fetchone()
		if x:
			return x[0]
			
	def broadcastUpdate(self, addr= (MCAST_GRP,MCAST_PORT)):
		"Anounce what the tip of the modified chain is, to everyone"
		print("bcaststart")
		if not localDiscovery:
			return
			
		#noServe has one special value Copy that enables this but dis
		
		if self.noServe==True:
			return
			
		d = self.getModifiedTip()
		print("to", addr)
		sendsock.sendto(("record\n"+b64encode(self.pubkey).decode("utf8")+"\n"+str(d)+"\n"+str(http_port)).encode("utf8"), addr)
	
	
	def hasRecordBeenDeleted(self,id,chain=b""):
		"Returns True, and also deletes the record for real, if it should be garbage collected because its unreachable"
		#The chain tip is obviously still good
		t = self.getChainTip(chain)
		if id==t:
			return False
	
		#Something still refers to it
		if self.hasReferrent(id,chain):
			return False
		
		#Delete the record for real, so it doesn't trouble us anymore
		self.conn.execute("DELETE FROM record WHERE id=? AND chain=?",(id,chain))
		return True
		
	
	def hasReferrent(self,id,chain=b''):
		"Returns true if a block in the chain references the given ID"
		c=self.conn.cursor()
		c.execute("SELECT * FROM record WHERE prev=? AND chain=?",(id,chain))
		return c.fetchone()	
		
	def getPrev(self,id,chain=b''):
		"Returns the previous block in the chain"
		c=self.conn.cursor()
		c.execute("SELECT prev FROM record WHERE prev=? AND chain=?",(id,chain))
		x= c.fetchone()
		if x:
			return x[0]
		return 0
			
	def getRecordById(self,id,chain=b''):
		c=self.conn.cursor()
		c.execute("SELECT * FROM record WHERE id=? AND chain=?",(id,chain))
		return c.fetchone()
			
	def getChainTip(self,chain=b''):
		"Gets the record at the tip of the record chain"
		c=self.conn.cursor()
		c.execute("SELECT id FROM record WHERE chain=? ORDER BY id DESC",(chain,))
		x=c.fetchone()
		if not x==None:
			return x[0]
		return 0
		
	def getChainBackPointer(self,chain=b""):
		"Gets whatever the back record is pointing to. If it's not 0, we don't have full history"
		c=self.conn.cursor()
		c.execute("SELECT prev FROM record WHERE chain=? ORDER BY id ASC",(chain,))
		x=c.fetchone()
		if not x==None:
			return x[0]
		return 0
		
	def getRecordsSince(self,t):
		"Gets the cursor that can iterate over a certain number of records. Returns records for all chains"
		c=self.conn.cursor()
		c.execute("SELECT * FROM record WHERE modified>? ORDER BY id ASC",(t,))
		return c


	def getModifiedTip(self,chain=b""):
		"Get the most recently modified records's modified time"
		c=self.conn.cursor()
		c.execute("SELECT modified FROM record WHERE chain=? ORDER BY id DESC",(chain,))
		x=c.fetchone()
		if x:
			return x[0]
		return 0
		
		
	def savePK(self):
		if self.fn:
			with open(self.fn+".privatekey",'w') as f:
				f.write(b64encode(self.privkey).decode("utf8"))
			##TODO: Race condition, some bad guy can spy before we write	
			os.chmod(self.fn+".privatekey", 0o600)

	def getAttr(self,k):
		c=self.conn.cursor()
		c.execute("SELECT value FROM attr WHERE key=?", (k,))
		x=c.fetchone()
		if x:
			return x[0]
			
	def setAttr(self,k,v):
		with self.conn:
			self.conn.execute("DELETE FROM attr WHERE key=?",(k,))
			self.conn.execute("INSERT INTO attr VALUES (?,?)",(k,v))
		 




fullSyncInterval = 7200
lastDidFullSync= time.time()

def drayerServise():
	global lastDidFullSync
	
	while 1:
		#This failing is just a normal expected thing. We won't always be able to access everything.
		try:
			if time.time()-lastDidFullSync>fullSyncInterval:
				for i in _allStreams:
					try:
						i.sync()
					except:
						pass
		except:
			pass
		
		#Past this point is LAN stuff
		if not localDiscovery:
			time.sleep(1)
			continue
			
		rd,w,x= select.select([sendsock,listensock],[],[], 30)
		for i in rd:
			b, addr = i.recvfrom(64000)
			print(b)
			
			d = b.decode("utf8").split("\n")
			
			"""
			getRecordsSince
			PUBKEY
			time
			"""
			#response
			"""
			record
			PUBKEY
			timestamp
			HTTP PORT
			"""
			
			if d[0] == "getRecordsSince":
				if b64decode(d[1]) in _allStreams:
					try:
						
						x= _allStreams[b64decode(d[1])].getThreadCopy()			
						h = x.getRecordsSince(int(d[2])).fetchone()
						if not h:
							continue
						h = h["modified"]
						
						x.broadcastUpdate(addr)
					finally:
						del x
						
			if d[0] == "record":
				print(d)
				if b64decode(d[1]) in _allStreams:
					try:
						x= _allStreams[b64decode(d[1])].getThreadCopy()
						if int(d[2])> x.getModifiedTip():
							x.sync("http://"+addr[0]+":"+d[3])
					finally:
						del x
					


thr = threading.Thread(target=drayerServise, daemon=True)
thr.daemon=True
localDiscovery=False
thr.start()

def startLocalDiscovery():
	global localDiscovery
	localDiscovery = True

def openRouterPort():
	"Open a port on the local router, making cherrypy's HTTP server TOTALLY PUBLIC"
	from . import handleupnp
	handleupnp.addMapping(http_port, "TCP", "Drayer HTTP protocol")

torrentServer=None

def startBittorent():
	import btdht
	global torrentServer
	torrentServer = btdht.DHT()
	torrentServer.start()
	
def startServer():
	global http_port
	
	cherrypy.tree.mount(DrayerWebServer(), '/',{})
	
	for i in range(0,40):
		try:
			cherrypy.engine.start()
			break
		except:
			if i==39:
				raise
			#Trying random ports till we find a good one
			http_port = random(8000, 48000)
