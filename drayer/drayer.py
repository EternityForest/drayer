
import libnacl,os,sqlite3,struct,time,weakref,msgpack,requests, socket,threading,select,urllib,random,traceback

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
		c = _allStreams[b64decode(streampk)].getRecordsSince(t)
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
		
		self.lastSynced = 0
		self.lastDHTAnnounce =0 
		
		#Keep track of which of the primary servers we sync with,
		#if there are any
		self.selectedServer= None
		
		self.tloc = threading.local()

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
	
	def getConn(self):
		try:
			return self.tloc.conn
		except:
			self.tloc.conn=sqlite3.connect(self.fn)
			self.tloc.conn.row_factory = sqlite3.Row
			return self.tloc.conn

	
	def getBytesForSignature(self, id,key,h, modified, prev,prevchanged):
		#This is currently the definition of how to make a signature
		return struct.pack("<QqqqL", id,modified,prev, prevchanged,len(key))+key.encode("utf8")+h
	
	def makeSignature(self, id,key, h, modified, prev,prevchanged,chain=None):
		if not chain == self.pubkey:
			if chain:
				raise ValueError("Can only sign messages on the local chain")
		d = self.getBytesForSignature(id,key,h, modified, prev,prevchanged)
		return libnacl.crypto_sign_detached(d, self.privkey)
		
	
	def setPrimaryServers(self, servers):
		self["__drayer_primary_servers__"] = msgpack.packb(servers)
		
	def getPrimaryServers(self):
		#Returns a list of trusted primary servers.
		#When syncing, we should sync to one of them.
		return msgpack.unpackb(self["__drayer_primary_servers__"])
		
	def sync(self,url=None):
		"""Syncs with a remote server"""
		#Don't sync too often
		if self.lastSynced>(time.time()-60):
			return
		self.lastSynced = time.time()
		
		inserted = 0
		
		for chain in self.getSiblingChains():
			if url:
				if url.startswith("http"):
					inserted+=self.httpSync(url,chain)
			
			if not self.selectedServer:
				try:
					s =self.getPrimaryServers()
					#Filter by what we know how to handle
					s = {i:s[i] for i in s if s[i]["type"]=="http"}
					self.selectedServer = random.choice(s)
				except KeyError:
					self.selectedServer = None
				
				
			if self.selectedServer:
				#If we can sync with a primary trusted server, we have no need to mess with
				#random bittorrent DHT nodes that are probabl
				try:
					self.httpSync(self.selectedServer["url"],chain)
					return
				except:
					#If it was unreachable, pick a new server
					self.selectedServer=None
					pass
					
			
			if torrentServer:
				bthash=libnacl.crypto_generichash(chain)
				bthash=libnacl.crypto_generichash(bthash)[:20]			
				#Sync with 5 random DHT nodes. We just hope that eventually we will
				#get good data.
				x = torrentServer.get_peers(bthash)
				random.shuffle(x)
				if x:
					for i in x[:5]:
						try:
							inserted+=self.directHttpSync(i[0],i[1],chain)
						except:
							print(traceback.format_exc())
						
					
			if localDiscovery:
				sendsock.sendto(msgpack.packb({
				"type":"getRecordsSince",
				"chain":chain,
				"time": self.getModifiedTip()}), (MCAST_GRP,MCAST_PORT))
				
			if inserted:
				#If we actually got something reset the timer, there's might be more
				self.lastSynced = 0
				
	def directHttpSync(self,ip,port,chain=b''):
		"Use an ip port pair to sync"
		return self.httpSync("http://"+ip+":"+str(port),chain)

	def httpSync(self,url,chain=b''):
		"""Gets any updates that an HTTP server might have"""
		if url.endswith("/"):
			pass
		else:
			url+="/"
			
		#newRecords/PUBKEY/sinceTime
		r = requests.get(
				url+
				"newRecords/"+
				urllib.parse.quote_plus(b64encode(chain or self.pubkey).decode("utf8"))+
				"/"+str(self.getModifiedTip()
			),stream=True)
		r.raise_for_status()
		r=r.raw.read(100*1000*1000)
		
		r = msgpack.unpackb(r)
		
		#Haven't needed to read siblings yet
		siblings = None
		
		inserted =0
		for i in r:
			if i[b'chain']:
				if not siblings:
					siblings=self.getSiblingChains()
				if not chain in siblings:
					i[b'chain']
			try:
				#Internal compressed representation
				c = i[b'chain']
				if c==self.pubkey:
					c=b''
				self.insertRecord(i[b"id"],i[b"key"].decode("utf8"),i[b"val"], i[b"mod"], i[b"prev"], i[b"prevch"],i[b"sig"],c)
			except:
				print(traceback.format_exc())
				return inserted
			inserted+=1
		return inserted
			
	def checkSignature(self, id,key,h, modified, prev,prevchanged, sig,chain=None):
		d = self.getBytesForSignature(id,key,h, modified, prev,prevchanged)
		return libnacl.crypto_sign_verify_detached(sig, d, chain or self.pubkey)
	
	def isSiblingAtTime(self,chain,t):
		"Return true if the given chain was considered a sibling at the given time"
		if chain==b"":
			#Local chain is always in the set
			return True
		c = self.getSiblingChains()
		if chain in c:
			if time.time()>=c[chain][1]:
				#non expiring
				if not c[chain][2]:
					return True
					
				if time.time()<=c[chain][2]:
					return True
					
				
	def getSiblingChains(self):
		"""Return a dict of all sibling chains, including ones referenced BY sibling chains that have not been synced yet.
			dict entries returned as:
			
			pubkey(bin): entrytimestamp, validstart(0 for never), validend(0 for none)
					
			Nodes merge in records from other nodes,and later entrytimestamps take priority.
			We have no way to really delete these records, just to leave an invalid marker.
			
			However, we have a special reseved entry. A pubkey value of b"COMPLETE" declares
			that there are no period entries older than that which are still valid.
			
			To make things easier, only one period per key.
			Sibl
			The actual DrayerSiblings record format is just a list of msgpack dicts.
		"""	
		
		#TODO: actually implement this
		
		c=self.getConn().cursor()
		
		#Note that we read from all siblings. The sibling of our sibling is also our sibling.
		c.execute('SELECT id FROM record WHERE key="__drayer_siblings__"')
		#We're always included in our own
		periods = {self.pubkey:{0,0,0}}
		
		#This is a really slow process of reading things. We probably need to cache this somehow.
		for i in c:
			self.validateRecord(i["id"], i["chain"])
			#Get all the records
			value = msgpack.unpackb(i["value"])
			for j in value:
				if j[b"pubkey"] in periods:
					if j[b"timestamp"] > periods[j[b"pubkey"]][b"timestamp"]:
							periods[j[b"pubkey"]] = j
				else:
					periods[i[b"pubkey"]] = j
			torm=[]
		
		#After we have everything, delete the 
		#Records that have been deleted by COMPLETEs.
		for j in periods:
			if periods[j][b"pubkey"]== b'COMPLETE':
				for k in periods:
					if periods[k][b"timestamp"]< periods[j][b"timestamp"]:
						torm.append(k)
		for i in torm:
			del periods[i]
			
		#TODO: Actually delete the unneeded stuff, and merge all the siblings into one
		#which we then write back to the main chain
		
		
		return {i:(periods[i][b"timestamp"], periods[i][b"from"],periods[i][b"to"]) for i in periods}
						
			
	def validateRecord(self,id, chain=b""):
		##Make sure a record is actually supposed to be there
		x = self.getRecordById(id,chain)
		
		if not self.isSiblingAtTime(x["chain"],x["modified"]):
			raise RuntimeError("Record belongs to a chain that is/was not the local chain or a sibling when it was made")

		h= libnacl.crypto_generichash(x["value"])
		if not h==x["hash"]:
			raise RuntimeError("Bad Hash")
		

		self.checkSignature(id,x["key"], h,x["modified"], x["prev"],x["prevchange"], x["signature"],chain)
		if self.hasRecordBeenDeleted(id,chain):
			raise RuntimeError("Record appears valid but was deleted by a later change")

		
		
		
	def insertRecord(self, id,key,value, modified, prev,prevchanged, signature, chain=b""):
		print("inserting",key, id, prev,modified,prevchanged)
		
		#TODO: Removing peers is super confusing. We'll refuse to add any more to their chains.
		#But if there's already messages will there be race conditions?
		if not self.isSiblingAtTime(chain, modified):
				raise RuntimeError("Chain must be local chain or a sibling")
		
		if chain==self.pubkey:
			chain=b''
			
		#Most basic test, make sure it's signed correctly
		
		#We don't supply a hash because we check it here anyway
		h= libnacl.crypto_generichash(value)
		self.checkSignature(id,key, h,modified, prev,prevchanged, signature,chain)
	
		#The thing that the old block that we might be replacing used to point at
		oldPrev = self.getPrev(id,chain)
		

		mtip = self.getModifiedTip(chain)
		
		#TODO:Back of chain connections
		if modified<= mtip:
			raise RuntimeError("Modified time cannot be before the tip of the chain")
			
		if not self.getRecordByModificationTime(prevchanged,chain):
			#The new block has to connect SOMEWHERE on the chain but not necessearily 
			#the end, so it can "patch stuff out".
		
			#Always allow the special case of the thing that's supposed to point at the very start,
			#Imaginary block 0.
			if prevchanged:
				#And of course we have the exception for linking to the back
				raise ValueError("New records must connect to an existing value in the mchain, or must connect to the back of the chain.")
		
		tip = self.getChainTip(chain)
		
		if not prev ==tip:
			if not self.getRecordById(id,chain):
				#Also, we can append to the back
				if not self.getChainBackPointer(chain)==id:
					raise ValueError("New records must modify an existing entry, or append to one of the ends")
			
				
		with self.getConn():
			oldRecord = self.getRecordById(id, chain)
			#If we are overwriting a record that had something pointing to it,
			#We're going to silently patch what it pointed to, and we aren't going to tell anyone unless they ask.
			
			#See the readme for why we can get away with this. It's because past state of the modified
			#chain doesn't matter, only the last block. Anyone getting new data gets the new,
			#anyone else doesn't care
			if oldRecord:				
				n = self.getNextModifiedRecord(oldRecord["modified"],chain)
				if n:
					p = oldRecord["prevchange"]
					#Whatever is in front of us needs to point to what's behind us.
					sig=self.makeSignature(n["id"],n["key"],n["hash"],n["modified"],n["prev"],n["prevchange"],chain)
					self.getConn().execute("UPDATE record SET prevchange=?,signature=? WHERE id=? AND chain=?",(p, sig,n["id"], chain))
				self.getConn().execute("DELETE FROM record WHERE id=? AND chain=?",(id,chain))
			
			
			self.getConn().execute("INSERT INTO record VALUES(?,?,?,?,?,?,?,?,?)",(id,key,value,h,modified,prev,prevchanged, signature,chain))
			
			
			#Now, in a completely different chain, we se if anything has been "patched out" of it.
			if oldPrev:
				if not oldPrev==prev:
					#If we changed prev we need to garbage collect the unreachable node.
					self.hasRecordBeenDeleted(oldPrev,chain)
					
					
	def __delitem__(self,k):
		id = self.getIdForKey(k)
		with self.getConn():
			if not id:
				raise KeyError(k)
				
			#The record that references us in the actual chain
			#That we are going to patch to not do that
			n = self.getNextRecord(id)
			
			if not n:
				#The block tip can's be GCed so we can't delete it
				raise RuntimeError("Currently we cannot delete the very most recently added item, but you can add another and try again.")

			p = self.getPrev(id)
			mtip = self.getModifiedTip()
			
			torm = self.getRecordById(id)
			
			#We cannot have a record that connects to itself...
			if mtip == n["modified"]:
				mtip =n['prevchange']
			
			#Can't connect to the one we're about to delete either
			if mtip== torm['modified']:
				x = self.getRecordByModificationTime(torm["prevchange"])
				if not x:
					if not torm["prevchange"]==0:
						#There would be nothing for the record to connect to!
						raise RuntimeError("Can't remove that record")
				mtip=torm["prevchange"]
			
			
			#Make a new record for the one right in front of it.
			#insertRecord will handle patching the one in front of *that*
			t = int(time.time()*1000000)
			sig=self.makeSignature(n["id"],n["key"], n["hash"],t,p,mtip)
			self.insertRecord(n["id"],n["key"],n["value"], t,p, mtip,sig)
			
		
			
					
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
		e = None
		#There could be multiple records for a key.
		#We should have deleted expired ones, but it may be that a no-longer-valid
		#Sibling has recent keys that will fail vaildation, and we want to return to our own verision
		
		#So we try records till we get a valid one
		for i in self.getRecordsForKey(k):
			try:
				self.validateRecord(i["id"],i["chain"])
				return self.filterGet(i["value"])
			except Exception as q:
				e=q
			
		raise e or KeyError(k)
		
	
	def filterInsert(self,k,v):
		"Preprocess values inserted with the dict insert style"
		return k,v
	
	def filterGet(self,v):
		return v
		
	def announceDHT(self,allChains=False):
		"Advertise this node on bittorrent"
		
		self.enable_dht = True
		
		#Rate limiting logic
		if self.lastDHTAnnounce>(time.time()-5*60):
			return
		self.lastDHTAnnounce = time.time()
		if self.noServe:
			raise RuntimeError("noServe is enabled for this object. Perhaps you meant to advertise from the main thread?")


		l = [self.pubkey]
		if allChains:
			l=self.getSiblingChains()
		for i in l:
			bthash=libnacl.crypto_generichash(i)
			bthash=libnacl.crypto_generichash(bthash)[:20]
			
			if torrentServer:
				torrentServer.get_peers(bthash)
				torrentServer.announce_peer(bthash, http_port,0,False)
			
		
	def getIdForKey(self, key):
		"Returns the ID of the most recent record with a given key"
		c=self.getConn().cursor()
		c.execute("SELECT id FROM record WHERE key=? ORDER BY modified desc",(key,))
		x = c.fetchone()
		if x:
			return x[0]
			
	def getRecordsForKey(self, key):
		"Returns all records for a key, most recent first"
		c=self.getConn().cursor()
		c.execute("SELECT * FROM record WHERE key=? ORDER BY modified desc",(key,))
		return c
			
	def broadcastUpdate(self, addr= (MCAST_GRP,MCAST_PORT),chain=b""):
		
		"Anounce what the tip of the modified chain is, to everyone"
		print("bcaststart")
		
		if not localDiscovery:
			return
			
		#noServe has one special value Copy that enables this but dis
		if self.noServe==True:
			return
		
		i= self.getModifiedTipRecord(chain)
		if not i:
			return
		chain = chain or self.pubkey
		#sendsock.sendto(("record\n"+b64encode(self.pubkey).decode("utf8")+"\n"+str(d)+"\n"+str(http_port)).encode("utf8"), addr)
	
	
		sendsock.sendto(msgpack.packb({"type":"record",
				"hash":i["hash"],
				"key":i["key"],
				"id": i["id"],
				"sig":i["signature"],
				"prev":i["prev"],
				"prevch":i["prevchange"],
				"mod":i["modified"],
				"httpport": http_port,
				"chain":chain
				}),addr)
	
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
		self.getConn().execute("DELETE FROM record WHERE id=? AND chain=?",(id,chain))
		print("Garbage collected")
		return True
		
	
	def hasReferrent(self,id,chain=b''):
		"Returns true if a block in the chain references the given ID"
		c=self.getConn().cursor()
		c.execute("SELECT * FROM record WHERE prev=? AND chain=?",(id,chain))
		return c.fetchone()	
		
	def getPrev(self,id,chain=b''):
		"Returns the id of the previous block in the chain"
		c=self.getConn().cursor()
		c.execute("SELECT prev FROM record WHERE id=? AND chain=?",(id,chain))
		x= c.fetchone()
		if x:
			return x[0]
		return 0
		
	def getNextRecord(self,id,chain=b''):
		"Returns the previous block in the chain"
		c=self.getConn().cursor()
		c.execute("SELECT * FROM record WHERE prev=? AND chain=?",(id,chain))
		x= c.fetchone()
		if x:
			return x
		return 0	

	def getNextModifiedRecord(self,t,chain=b''):
		"Returns the next block in the modified chain"
		c=self.getConn().cursor()
		c.execute("SELECT * FROM record WHERE prevchange=? AND chain=?",(t,chain))
		x= c.fetchone()
		if x:
			return x
		return None
	
	def getRecordByModificationTime(self,t,chain=b''):
		"Returns the next block in the modified chain"
		c=self.getConn().cursor()
		c.execute("SELECT * FROM record WHERE modified=? AND chain=?",(t,chain))
		x= c.fetchone()
		if x:
			return x
		return 0	
		
	def getRecordById(self,id,chain=b''):
		c=self.getConn().cursor()
		c.execute("SELECT * FROM record WHERE id=? AND chain=?",(id,chain))
		return c.fetchone()
			
	def getChainTip(self,chain=b''):
		"Gets the record at the tip of the record chain"
		c=self.getConn().cursor()
		c.execute("SELECT id FROM record WHERE chain=? ORDER BY id DESC",(chain,))
		x=c.fetchone()
		if not x==None:
			return x[0]
		return 0
		
	def getChainBackPointer(self,chain=b""):
		"Gets whatever the back record is pointing to. If it's not 0, we don't have full history"
		c=self.getConn().cursor()
		c.execute("SELECT prev FROM record WHERE chain=? ORDER BY id ASC",(chain,))
		x=c.fetchone()
		if not x==None:
			return x[0]
		return 0
		
	def getRecordsSince(self,t):
		"Gets the cursor that can iterate over a certain number of records. Returns records for all chains"
		c=self.getConn().cursor()
		c.execute("SELECT * FROM record WHERE modified>? ORDER BY id ASC",(t,))
		return c


	def getModifiedTip(self,chain=b""):
		"Get the most recently modified records's modified time"
		c=self.getConn().cursor()
		c.execute("SELECT modified FROM record WHERE chain=? ORDER BY id DESC",(chain,))
		x=c.fetchone()
		if x:
			return x[0]
		return 0
		
	def getModifiedTipRecord(self,chain=b""):
		"Get the most recently modified records's modified time"
		c=self.getConn().cursor()
		c.execute("SELECT * FROM record WHERE chain=? ORDER BY id DESC",(chain,))
		x=c.fetchone()
		if x:
			return x
		
	def savePK(self):
		if self.fn:
			with open(self.fn+".privatekey",'w') as f:
				f.write(b64encode(self.privkey).decode("utf8"))
			##TODO: Race condition, some bad guy can spy before we write	
			os.chmod(self.fn+".privatekey", 0o600)

	def getAttr(self,k):
		c=self.getConn().cursor()
		c.execute("SELECT value FROM attr WHERE key=?", (k,))
		x=c.fetchone()
		if x:
			return x[0]
			
	def setAttr(self,k,v):
		with self.getConn():
			self.getConn().execute("DELETE FROM attr WHERE key=?",(k,))
			self.getConn().execute("INSERT INTO attr VALUES (?,?)",(k,v))
		 




fullSyncInterval = 7200
lastDidFullSync= time.time()

#When was the last time we re announced all nodes to the DHT?
lastDidAnnounce=time.time()

def isLocal(i):
	if i.startswith("192."):
		return True
	if i.startswith("10."):
		return True
	if i.startswith("127."):
		return True
	if i.startswith("192.168"):
		return True
	if i.startswith("172."):
		x= int(i.split(".")[1])
		if x<16:
			return False
		if x>31:
			return False
		return True
	if i.startswith("fd"):
		return True
	if i.startswith("fc"):
		return True
		
	return False
		



def drayerServise():
	global lastDidFullSync,lastDidAnnounce
	
	while 1:
		#This failing is just a normal expected thing. We won't always be able to access everything.
		try:
			if time.time()-lastDidFullSync>fullSyncInterval:
				lastDidFullSync=time.time()
				for i in _allStreams:
					try:
						_allStreams[i]._serviceCopy().sync()
					except:
						print(traceback.format_exc())

		except:
			print(traceback.format_exc())

		
		#Redo DHT announce every ten minutes for all nodes that need it
		try:
			if time.time()-lastDidAnnounce>10*60:
				lastDidAnnounce = time.time()
				for i in _allStreams:
					try:
						if _allStreams[i].enable_dht:
							_allStreams[i].serviceCopy().announceDHT()
					except:
						print(traceback.format_exc())

		except:
			print(traceback.format_exc())

		
		#Past this point is LAN stuff
		if not localDiscovery:
			time.sleep(1)
			continue
			
		rd,w,x= select.select([sendsock,listensock],[],[], 30)
		for i in rd:
			b, addr = i.recvfrom(64000)
			
			try:
				d=msgpack.unpackb(b)				
				if d[b"type"] == b"getRecordsSince":
					if d[b"chain"] in _allStreams:
						try:
							x= _allStreams[d[b"chain"]]
							#Internally we use empty strings to mean the local chain	
							if	d[b"chain"] == x.pubkey:
								chain = b''
							else:
								chain = d[b"chain"]
							h = x.getModifiedTip(chain)
							if h==None:
								continue
							if h>d[b"time"]:
								x.broadcastUpdate(addr)
						finally:
							del x
							
				if d[b"type"] == b"record":
					#If we allowed random people on the internet to tell us to make HTTP
					#requests we'd be the perfect DDoS amplifier
					#So we block anything that isn't local.
					if not isLocal(addr[0]):
						continue
						
					if d[b"chain"] in _allStreams:
						try:

								
							x= _allStreams[d[b"chain"]]
							
							#Internally we use empty strings to mean the local chain	
							if	d[b"chain"] == x.pubkey:
								chain = b''
							else:
								chain = d[b"chain"]
								
							if d[b"mod"]> x.getModifiedTip():
								x.httpSync("http://"+addr[0]+":"+str(d[b"httpport"]),chain)
						finally:
							del x
			except:
				print(traceback.format_exc())


thr = threading.Thread(target=drayerServise, daemon=True)
thr.daemon=True
localDiscovery=False
thr.start()

def startLocalDiscovery():
	global localDiscovery
	localDiscovery = True


isRouterPortOpen = False

def openRouterPort():
	"Open a port on the local router, making cherrypy's HTTP server TOTALLY PUBLIC"
	global isRouterPortOpen
	isRouterPortOpen = True
	
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
