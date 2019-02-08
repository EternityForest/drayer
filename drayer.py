
import libnacl,os,sqlite3,struct,time

from base64 import b64decode, b64encode

class DrayerStream():
	def __init__(self, fn=None, pubkey=None):
		
		if pubkey:
			pubkey=b64decode(pubkey)
		
		self.pubkey = None
		self.fn = fn
	
		if fn:
			self.conn=sqlite3.connect(fn)
			c=self.conn.cursor()
			#This is just a basic key value table for really simple basic info about the
			#Stream
			c.execute("CREATE TABLE IF NOT EXISTS attr (key text, value text);")
			
			#This is the actual record chain
			## id: Numeric incrementing ID
			##key, value: same meaning as any other dict
			#modified: Modification date, microsecods since unix
			#prev: Pointer to the previous block in the chain. Points to the ID.
			#prevchanged: At the time this block was last changed, it points to the previous most recent modified date
			c.execute("CREATE TABLE IF NOT EXISTS record (id integer primary key, key text, value text, modified integer, prev integer, prevchange integer, signature blob);")

			pk = self.getAttr("PublicKey")
			print("PK found")
			if pk:
				self.pubkey = b64decode(pk)
				if pubkey and not(pk==pubkey):
					raise ValueError("You specified a pubkey, but the file already contains one that does not match")
			else:
				vk, sk = libnacl.crypto_sign_keypair()
				self.setAttr("PublicKey", b64encode(vk).decode("utf8"))
				self.pubkey = vk
				self.privkey = sk
				self.savePK()
				
			if os.path.exists(fn+".privatekey"):
				with open(fn+".privatekey") as f:
					self.privkey = b64decode(f.read())
					
	
	
	
	def getBytesForSignature(self, id,key,value, modified, prev,prevchanged):
		#This is currently the definition of how to make a signature
		return struct.pack("<QqqqL", id,modified,prev, prevchanged,len(key))+key.encode("utf8")+value
	
	def makeSignature(self, id,key,value, modified, prev,prevchanged):
		d = self.getBytesForSignature(id,key,value, modified, prev,prevchanged)
		return libnacl.crypto_sign_detached(d, self.privkey)
		
		
		
	def checkSignature(self, id,key,value, modified, prev,prevchanged, sig):
		d = self.getBytesForSignature(id,key,value, modified, prev,prevchanged)
		return libnacl.crypto_sign_verify_detached(sig, d, self.pubkey)
		
		
	def insertRecord(self, id,key,value, modified, prev,prevchanged, signature):
		#Most basic test, make sure it's signed correctly
		self.checkSignature(id,key,value, modified, prev,prevchanged, signature)
		
		#The thing that the old block that we might be replacing used to point at
		oldPrev = self.getPrev(id)
		
		mtip = self.getModifiedTip()
		if not prevchanged == mtip:
			raise ValueError("New records must connect to the previous modified value")
		
		tip = self.getChainTip()
		
		if not prev ==tip:
			if not self.getRecordById(id):
				raise ValueError("New records must modify an existing entry, or append to the end")
				
		with self.conn:
			self.conn.execute("DELETE FROM record WHERE id=?",(id,))
			self.conn.execute("INSERT INTO record VALUES(?,?,?,?,?,?,?)",(id,key,value,modified,prev,prevchanged, signature))
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
		print(id,k,v,mtime,prev,prevMtime)
		sig = self.makeSignature(id,k,v,mtime,prev,prevMtime)
		self.insertRecord(id,k,v,mtime,prev,prevMtime,sig)
		
	def __getitem__(self,k):
		id = self.getIdForKey(k)
		if id==None:
			raise KeyError(k)
		
		id,key,value,mtime,prev,prevmtime,sig= self.getRecordById(id)
		self.checkSignature(id, key,value, mtime,prev,prevmtime,sig)
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
		if hasReferrent(id):
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
		 

d = DrayerStream("fooo.stream")
print (d.getAttr("PublicKey"))
d["foo"] = b"testing"
print(d["foo"])
