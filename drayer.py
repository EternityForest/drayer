
import libnacl,os,sqlite3,struct,time,weakref,msgpack,requests

from base64 import b64decode, b64encode

import cherrypy

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
				"mod":i["modified"]
			})
	
		x= msgpack.packb(l)
		return(x)
			
		
		
		
cherrypy.config.update({'server.socket_port': 9698})

_allStreams = weakref.WeakValueDictionary()




class DrayerStream():
	def __init__(self, fn=None, pubkey=None,noServe=False):
		
		if pubkey:
			if isinstance(pubkey, str):
				pubkey=b64decode(pubkey)
		
		self.pubkey = None
		self.fn = fn
	
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
			#prevchanged: At the time this block was last changed, it points to the previous most recent modified date
			c.execute("CREATE TABLE IF NOT EXISTS record (id integer primary key, key text, value blob, hash blob, modified integer, prev integer, prevchange integer, signature blob);")

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
					
			if not noServe:
				_allStreams[self.pubkey] = self
	
	
	def getThreadCopy(self):
		"Returns another DrayerStream that should be open to the same db"
		return DrayerStream(self.fn,self.pubkey,True)
	
	
	def getBytesForSignature(self, id,key,h, modified, prev,prevchanged):
		#This is currently the definition of how to make a signature
		return struct.pack("<QqqqL", id,modified,prev, prevchanged,len(key))+key.encode("utf8")+h
	
	def makeSignature(self, id,key, h, modified, prev,prevchanged):
		d = self.getBytesForSignature(id,key,h, modified, prev,prevchanged)
		return libnacl.crypto_sign_detached(d, self.privkey)
		
		
	
	def sync(self,url=None):
		"""Syncs with a remote server"""
		if url.startswith("http"):
			self.httpSync(url)
	
	def httpSync(self,url):
		"""Gets any updates that an HTTP server might have"""
		if url.endswith("/"):
			pass
		else:
			url+="/"
			
		#newRecords/PUBKEY/sinceTime
		r = requests.get(url+"newRecords/"+b64encode(self.pubkey).decode("utf8")+"/"+str(self.getModifiedTip()),stream=True)
		r.raise_for_status()
		r=r.raw.read(100*1000*1000)
		
		r = msgpack.unpackb(r)
		for i in r:
			self.insertRecord(i[b"id"],i[b"key"].decode("utf8"),i[b"val"], i[b"mod"], i[b"prev"], i[b"prevch"],i[b"sig"])
			
			
	def checkSignature(self, id,key,h, modified, prev,prevchanged, sig):
		d = self.getBytesForSignature(id,key,h, modified, prev,prevchanged)
		return libnacl.crypto_sign_verify_detached(sig, d, self.pubkey)
		
		
	def insertRecord(self, id,key,value, modified, prev,prevchanged, signature):
		#Most basic test, make sure it's signed correctly
		
		#We don't supply a hash because we check it here anyway
		h= libnacl.crypto_generichash(value)

		self.checkSignature(id,key, h,modified, prev,prevchanged, signature)
	
		#The thing that the old block that we might be replacing used to point at
		oldPrev = self.getPrev(id)
		
		mtip = self.getModifiedTip()
		if not prevchanged == mtip:
			#Obviously we have to allow anything at all to connect on to the very beginning.
			if mtip:
				#And of course we have the exception for linking to the back
				if self.getChainBackPointer()==id:
					raise ValueError("New records must connect to the previous modified value")
		
		tip = self.getChainTip()
		
		if not prev ==tip:
			if not self.getRecordById(id):
				#Tip is 0, we can start anywhere
				if tip:
					#Also, we can append to the back
					if self.getChainBackPointer()==id:
						raise ValueError("New records must modify an existing entry, or append to one of the ends")
				
				
		with self.conn:
			self.conn.execute("DELETE FROM record WHERE id=?",(id,))
			self.conn.execute("INSERT INTO record VALUES(?,?,?,?,?,?,?,?)",(id,key,value,h,modified,prev,prevchanged, signature))
			#Check if this comm
			if oldPrev:
				if not oldPrev==prev:
					#If we changed prev we need to garbage collect the unreachable node.
					hasRecordBeenDeleted(oldPrev)
					
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
		
	def __getitem__(self,k):
		id = self.getIdForKey(k)
		if id==None:
			raise KeyError(k)
		
		id,key,value,h,mtime,prev,prevmtime,sig= self.getRecordById(id)
		self.checkSignature(id, key,h, mtime,prev,prevmtime,sig)
		if not libnacl.crypto_generichash(value)==h:
			raise RuntimeError("Bad hash in database")
		if not self.hasRecordBeenDeleted(id):
			return self.filterGet(value)
		
		
	
	def filterInsert(self,k,v):
		"Preprocess values inserted with the dict insert style"
		return k,v
	
	def filterGet(self,v):
		return v
		
	def getIdForKey(self, key):
		"Returns the ID of the most recent record with a given key"
		c=self.conn.cursor()
		c.execute("SELECT id FROM record WHERE key=? ORDER BY modified desc",(key,))
		x = c.fetchone()
		if x:
			return x[0]
		
	def hasRecordBeenDeleted(self,id):
		"Returns True, and also deletes the record for real, if it should be garbage collected because its unreachable"
		#The chain tip is obviously still good
		t = self.getChainTip()
		if id==t:
			return False
	
		#Something still refers to it
		if self.hasReferrent(id):
			return False
		
		#Delete the record for real, so it doesn't trouble us anymore
		self.conn.execute("DELETE FROM record WHERE id=?",(id,))
		return True
		
	
	def hasReferrent(self,id):
		"Returns true if a block in the chain references the given ID"
		c=self.conn.cursor()
		c.execute("SELECT * FROM record WHERE prev=?",(id,))
		return c.fetchone()	
		
	def getPrev(self,id):
		"Returns the previous block in the chain"
		c=self.conn.cursor()
		c.execute("SELECT prev FROM record WHERE prev=?",(id,))
		x= c.fetchone()
		if x:
			return x[0]
		return 0
			
	def getRecordById(self,id):
		c=self.conn.cursor()
		c.execute("SELECT * FROM record WHERE id=?",(id,))
		return c.fetchone()
			
	def getChainTip(self):
		"Gets the record at the tip of the record chain"
		c=self.conn.cursor()
		c.execute("SELECT id FROM record ORDER BY id DESC")
		x=c.fetchone()
		if not x==None:
			return x[0]
		return 0
		
	def getChainBackPointer(self):
		"Gets whatever the back record is pointing to. If it's not 0, we don't have full history"
		c=self.conn.cursor()
		c.execute("SELECT prev FROM record ORDER BY id ASC")
		x=c.fetchone()
		if not x==None:
			return x[0]
		return 0
		
	def getRecordsSince(self,t):
		"Gets the cursor that can iterate over a certain number of records"
		c=self.conn.cursor()
		c.execute("SELECT * FROM record WHERE modified>? ORDER BY id ASC",(t,))
		return c


	def getModifiedTip(self):
		"Get the most recently modified records's modified time"
		c=self.conn.cursor()
		c.execute("SELECT modified FROM record ORDER BY id DESC")
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
		 





if __name__ == '__main__':
	d = DrayerStream("fooo.stream")
	d["foo2.0"] = b"testing"
	d["foo"] = b"testing"
	print(d["foo"])
	
	cherrypy.tree.mount(DrayerWebServer(), '/',{})
	cherrypy.engine.start()
	time.sleep(3)
	#Can only serve one per pubkey in a process
	d2 = DrayerStream("foooClone.stream", d.pubkey, noServe=True)
	d2.sync("http://localhost:9698/")
	print(d2["foo"])
