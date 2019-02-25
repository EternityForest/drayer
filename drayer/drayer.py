
import libnacl,os,sqlite3,struct,time,weakref,msgpack,requests, socket,threading,select,urllib,random,traceback
import logging,gzip, io,json
from base64 import b64decode, b64encode
import webbrowser

import cherrypy

http_port = 33125

MCAST_GRP = '224.7.130.8'
MCAST_PORT = 15723


PLAINTEXT_DRAYERUDP=b'\xab\xc1a)'
ENCRYPTED_DRAYERUDP=b'k\xae\xf5\x9b'

#UNUSED: Work on adding multiple nodes in one process
def DrayerNode():
    def __init__(self):
        self.http_port=33125

        self.t = threading.Thread(target=self.service,daemon=True)
        self.t.start()
    def startLocalDiscovery(self):
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
        self.listensock=listensock
        self.sendsock = sendsock



    def service(self):
        
        while 1:
            #This failing is just a normal expected thing. We won't always be able to access everything.
            try:
                if time.time()-self.lastDidFullSync>fullSyncInterval:
                    self.lastDidFullSync=time.time()
                    for i in  self.streams:
                        try:
                            self.streams[i]._serviceCopy().sync()
                        except:
                            print(traceback.format_exc())

            except:
                print(traceback.format_exc())

            
            #Redo DHT announce every ten minutes for all nodes that need it
            try:
                if time.time()-self.lastDidAnnounce>10*60:
                    self.lastDidAnnounce = time.time()
                    for i in self.streams:
                        try:
                            if self.streams[i].enable_dht:
                                self.streams[i].serviceCopy().announceDHT()
                        except:
                            print(traceback.format_exc())

            except:
                print(traceback.format_exc())

            
            #Past this point is LAN stuff
            if not self.localDiscovery:
                time.sleep(1)
                continue
                
            rd,w,x= select.select([self.sendsock,self.listensock],[],[], 30)
            for i in rd:
                b, addr = i.recvfrom(64000)
                
                try:
                    d=msgpack.unpackb(b)				
                    if d[b"type"] == b"getRecordsSince":
                        if d[b"chain"] in self.streams:
                            try:
                                x= self.streams[d[b"chain"]]
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
                            
                        if d[b"chain"] in self.streams:
                            try:
                                x= self.streams[d[b"chain"]]
                                
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


def drayer_hash(d):
    if not isinstance(d, bytes):
        raise TypeError
    return libnacl.crypto_generichash(d)

def readPGP():
    le,lo,rev ={},{},{}
    pgpfn = os.path.join(os.path.split(__file__)[0],"pgplist.txt")
    with open(pgpfn) as f:
        l = f.read().split("\n")
    for i in l:
        i=i.strip()
        h, e, o=i.split("\t")
        lo[int(h,16)]=o
        le[int(h,16)]=e
        rev[o]=int(h,16)
        rev[e]=int(h,16)
    return le,lo, rev

pgp_even,pgp_odd,pgp_lookup = readPGP()

def encodePGP(b):
    c=0
    o=[]
    for i in b:
        if not c%2:
            o.append(pgp_even[i])
        else:
            o.append(pgp_odd[i])
    return " ".join(o).lower()


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


import base64
import re

def decode_base64(data, altchars=b'+/'):
    """Decode base64, padding being optional.

    :param data: Base64 data as an ASCII byte string
    :returns: The decoded byte string.

    """
    data = re.sub(r'[^a-zA-Z0-9%s]+' % altchars, '', data)  # normalize
    missing_padding = len(data) % 4
    if missing_padding:
        data += '='* (4 - missing_padding)
    return base64.b64decode(data, altchars)




class DrayerWebServer(object):
    @cherrypy.expose
    def index(self):
        return "Hello World!"


    def _cp_dispatch(self,vpath):
        """Rewrite things that look like stream/opcode to look like opcode/stream"""
        stream=vpath.pop(0)
        op=vpath.pop(0)

        cherrypy.request.params["streampk"]= urllib.parse.unquote(stream)
        return getattr(self,op)


    ### ALL THESE ARE'T THE REAL URLS.
    ### They all take the public key as the first parameter,
    ### The real url is pubkey/functionname, it gets remapped by cp_dispatch



    @cherrypy.expose
    def newRecordAvailable(self,type,streampk,**kw):
        """List up to 250 records of the given type.
            Records start with the most recently created, and the after and before
            options can limit the range(They are unix timestamps)
        """

        x =[]
        streampk=decode_base64(streampk)
        if not len(streampk)==32:
            raise ValueError("PK must be 32 bytes")
        db = _allStreams[streampk]
        r = msgpack.unpackb(kw[b'record'])
        if not d[b'mod']> db.getModifiedTip():
            return
        #We don't even make the requests for invalid records
        db.checkSignature(r[b'id'],r[b'type'].decode("utf8"),r[b'key'].decode("utf8"),r[b'hash'],r[b'ts'], r[b'mod'], r[b'prev'], r[b'prevch'],r[b'sig'],chain,value=r[b'val'])
        db.sync(db.ipPortToUrl(cherrypy.request.address[0],kw['port']))

    @cherrypy.expose
    def newestRecordsJSON(self,type,streampk,**kw):
        """List up to 250 records of the given type.
            Records start with the most recently created, and the after and before
            options can limit the range(They are unix timestamps)
        """

        x =[]
        streampk=decode_base64(streampk)
        if not len(streampk)==32:
            raise ValueError("PK must be 32 bytes")
        db = _allStreams[streampk]
        
        c = db.getConn().cursor()
        c.execute('SELECT * FROM record WHERE type=? AND id >? AND id<? ORDER BY id desc LIMIT 250',(type, kw.get("after",0),kw.get("before",2**62)))

        for i in c:
            x.append([i['key'],i['modified']])
        return json.dumps(x)


    @cherrypy.expose
    def listRecordsJSON(self,type,streampk,**kw):
        """List up to 250 records of the given type.
            Records start with the most recently modified, and the after and before
            options can limit the range(They are unix timestamps)
        """

        x =[]
        streampk=decode_base64(streampk)
        if not len(streampk)==32:
            raise ValueError("PK must be 32 bytes")
        db = _allStreams[streampk]
        
        c = db.getConn().cursor()
        c.execute('SELECT * FROM record WHERE type=? AND id>? AND id<? ORDER BY modified desc LIMIT 250',(type, kw.get("after",0),kw.get("before",2**60)))

        for i in c:
            x.append([i['key'],i['id']])
        return json.dumps(x)

    

    @cherrypy.expose
    def rawwebacess(self, type, key,streampk):
        streampk=decode_base64(streampk)
        if not len(streampk)==32:
            raise ValueError("PK must be 32 bytes")
        
        #cherrypy.response.headers['Content-Type']="application/octet-stream"
        return _allStreams[streampk].rawGetItemByKey(key, type)	

    @cherrypy.expose
    def webAccess(self, *key,streampk):
        print(key,streampk)
        streampk=decode_base64(streampk)
        if not len(streampk)==32:
            raise ValueError("PK must be 32 bytes")
        key = "/".join(key)
        #cherrypy.response.headers['Content-Type']="application/octet-stream"
        f = _allStreams[streampk].rawGetItemByKey(key, "file")
        l = struct.unpack("<L",f[:4])[0]
        h = f[4:4+l]
        d=f[4+l:]
        h=msgpack.unpackb(h,raw=False)

        if "enc" in h:
            cherrypy.response.headers['Content-Encoding']=h['enc']

        return d

    @cherrypy.expose
    def crdr(self, old,streampk):
        """Asks the node for the block that points to old in the modified chain.
            We might need to patch the chain but not be able to by ourselves
            because we don't have the PK
        
        """
        streampk=decode_base64(streampk)
        st = _allStreams[streampk]
        with st.lock:
            if not len(streampk)==32:
                raise ValueError("PK must be 32 bytes")

            cherrypy.response.headers['Content-Type']="application/octet-stream"
            old=int(old)
            i = st.getChainRepair(old, streampk)
            x=({
                "hash":i["hash"],
                "type":i["type"],
                "key":i["key"],
                "val":i["value"],
                "id": i["id"],
                "sig":i["signature"],
                "prev":i["prev"],
                "prevch":i["prevchange"],
                'ts':i['timestamp'],
                "mod":i["modified"],
                "chain":streampk
            })
        
            x= msgpack.packb(x)
            return(x)
       
    @cherrypy.expose
    def newRecords(self, t,streampk):
        "Returns a msgpacked list of new records"
        streampk=decode_base64(streampk)
        if not len(streampk)==32:
            raise ValueError("PK must be 32 bytes")

        cherrypy.response.headers['Content-Type']="application/octet-stream"
        t = int(t)
        st = _allStreams[streampk]
        with st.lock:
            with st.getConn():
                c = st.getRecordsSince(t,streampk)
                limit = 100
                l = []
                for i in c:
                    st.validateRecord(i["id"],i["chain"])
                    if limit<1:
                        break
                        limit-=1
                    l.append({
                        "hash":i["hash"],
                        "type":i["type"],
                        "key":i["key"],
                        "val":i["value"],
                        "id": i["id"],
                        "sig":i["signature"],
                        "prev":i["prev"],
                        "prevch":i["prevchange"],
                        "ts":i["timestamp"],
                        "mod":i["modified"],
                        "chain": streampk
                    })
            
                x= msgpack.packb(l)
                return(x)
                
        
    
#Stream objects by key
_allStreams = weakref.WeakValueDictionary()

#Stream objects by double hash
_allStreams_dblhash = weakref.WeakValueDictionary()



class DrayerStream():
    def __init__(self, fn=None, pubkey=None,noServe=False):
        
        if pubkey:
            if isinstance(pubkey, str):
                pubkey=pubkey.strip()
                if len(pubkey)==64:
                    pubkey=b64decode(pubkey)
                else:
                    #Try to decode things entered as the PGP wordlist
                    pubkey=pubkey.lower()
                    pubkey=pubkey.split(" ")
                    pubkey = bytes([pgp_lookup[i] for i in pubkey])
        
        self.pubkey = None
        self.privkey = None
        self.fn = fn
        self.lock=threading.Lock()
        self.noServe = noServe
        
        self.lastSynced = 0
        self.lastDHTAnnounce =0

        self.allowCleartext=True

        #Enable pushing TO the dht 
        self.enable_dht = False
        
        #Keep track of which of the primary servers we sync with,
        #if there are any
        self.selectedServer= None
        
        self.tloc = threading.local()
        
        if fn:
            self.conn=sqlite3.connect(fn,isolation_level="EXCLUSIVE")
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
            #time: Actual timestamp of the data(Not the record itself), used for resolving
                # conflicts between the record and external data
            #modified: Modification date of the record, microsecods since unix
            #prev: Pointer to the previous block in the chain. Points to the ID.
            #prevchange: At the time this block was last changed, it points to the previous most recent modified date
            #chain: If empty, it's the default chain. But we can also store "sibling chains" in here. We
            #would list them by the public key.
             
            c.execute("CREATE TABLE IF NOT EXISTS record (id integer, type text, key text, value blob, hash blob,timestamp integer, modified integer, prev integer, prevchange integer, signature blob, chain blob, UNIQUE(chain,modified),UNIQUE(chain,prevchange));")

            self.pubkey=pubkey
            pk = self.getAttr("PublicKey")
            if pk:
                pk = b64decode(pk)
            if pubkey and pk and not(pk==pubkey):
                    raise ValueError("You specified a pubkey, but the file already contains one that does not match")
                    
            if pk:
                self.pubkey = pk
            else:
                if not self.pubkey:
                    #No pubkey in the file or in the input, assume they want to make a new
                    vk, sk = libnacl.crypto_sign_keypair()
                    self.setAttr("PublicKey", b64encode(vk).decode("utf8"))
                    self.pubkey = vk
                    self.privkey = sk
                    if not os.path.exists(fn+".privatekey"):
                        self.savePK()
                    else:
                        raise RuntimeError("Refusing to overwrite PK")
                else:
                    #Get the pubkey from user
                    self.setAttr("PublicKey", b64encode(pubkey).decode("utf8"))
                    self.pubkey = pubkey
                    self.privkey = None
                
            if os.path.exists(fn+".privatekey"):
                with open(fn+".privatekey") as f:
                    self.privkey = b64decode(f.read())

            if self.privkey:
                #Make sure privkey is good so we don't wate our time
                x = libnacl.crypto_sign_detached(b"test", self.privkey)
                libnacl.crypto_sign_verify_detached(x,b'test', self.pubkey)

            if noServe==False:
                _allStreams[self.pubkey] = self

                _allStreams_dblhash=drayer_hash(drayer_hash(self.pubkey))
    
    def pgpFingerprint(self):
        return encodePGP(self.pubkey[:24])


    
    def getConn(self):
        try:
            return self.tloc.conn
        except:
            self.tloc.conn=sqlite3.connect(self.fn)
            self.tloc.conn.row_factory = sqlite3.Row
            return self.tloc.conn

    def pushToPrimary(chain=b''):
        x = self.getPrimaryServers()

        i= self.getModifiedTipRecord(chain)
        if not i:
            return
        chain = chain or self.pubkey
        d = msgpack.packb({"type":i['type'],
                "hash":i["hash"],
                "key":i["key"],
                "id": i["id"],
                "sig":i["signature"],
                "prev":i["prev"],
                "prevch":i["prevchange"],
                "mod":i["modified"],
                "httpport": http_port,
                "chain":chain
                })

        for s in x:
            requests.get(s['url']+base64.b64encode(chain).decode("utf8")+"/newRecordAvailable", record=d, port=self.http_port)


    def importFiles(self, dir, deletemissing=False, limit=50*1024*1024):
        if not os.path.exists(dir):
            raise RuntimeError("Bad dir")
        if not dir.endswith("/"):
            dir +="/"

        for b,d,f in os.walk(dir):
            for i in f:
                fn = os.path.join(b,i)
                if os.path.getsize(fn)>limit:
                    continue

                relpath = fn[len(dir):]
                self.insertFile(relpath, fn)

        if deletemissing:
            c=self.getConn().cursor()
            c.execute('SELECT key from record where type="file"')
            torm = []
            for i in c:
                if not os.path.exists(os.path.join(dir,i[0])):
                    torm.append(i[0])
            c.close()
            for i in torm:
                try:
                    self.rawDelete(i,"file")
                except:
                    logging.exception("Failed to delete file "+i)

    def onChange(self,action,id,key, chain):
        pass

    def getBytesForSignature(self, id,type,key,h,timestamp, modified, prev,prevchanged):
        #This is currently the definition of how to make a signature
        return struct.pack("<Qqqqq", id,timestamp,modified,prev, prevchanged)+drayer_hash(key.encode("utf8"))+h+drayer_hash(type.encode("utf8"))
    
    def makeSignature(self, id,type,key, h, timestamp,modified, prev,prevchanged,chain=None):
        if not chain == self.pubkey:
            if chain:
                raise ValueError("Can only sign messages on the local chain")
        d = self.getBytesForSignature(id,type, key,h,timestamp, modified, prev,prevchanged)
        return libnacl.crypto_sign_detached(d, self.privkey)
        
    
    def setPrimaryServers(self, servers):
        self.rawSetItem("primaryServers", msgpack.packb(servers,use_bin_type=True), "drayer")
        
    def getPrimaryServers(self):
        #Returns a list of trusted primary servers.
        #When syncing, we should sync to one of them.
        if self.keyExists("primaryServers","drayer"):
            return msgpack.unpackb(self.rawGetItemByKey("primaryServers","drayer"),raw=False)
        return []

    def sync(self,url=None):
        """Syncs with a remote server"""
        #Don't sync too often
        if self.lastSynced>(time.time()-60):
            return
        self.lastSynced = time.time()
        
        inserted = 0

        if self.privkey and url and url.startswith("file://"):
            url=url[len("file://"):]
            self.importFiles(url, deletemissing=True)
            #Mark as already used the url
            url=None
        
        for chain in self.getSiblingChains():
            if url:
                if url.startswith("http"):
                    inserted+=self.httpSync(url,chain)
            
            if not self.selectedServer:
                try:
                    s =self.getPrimaryServers()
                    if s:
                        #Filter by what we know how to handle
                        s = [i for i in s if i["type"]=="http"]
                        self.selectedServer = random.choice(s)
                        logging.debug("Selected server: "+self.selectedServer['url'])
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
                    print(traceback.format_exc())
                    pass
                    
            
            if torrentServer:
                bthash=drayer_hash(chain)
                bthash=drayer_hash(bthash)[:20]			
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
                sendsock.sendto(PLAINTEXT_DRAYERUDP+msgpack.packb({
                "mtype":"getRecordsSince",
                "chain":chain,
                "time": self.getModifiedTip()}), (MCAST_GRP,MCAST_PORT))
                
            if inserted:
                #If we actually got something reset the timer, there's might be more
                self.lastSynced = 0
                
    def directHttpSync(self,ip,port,chain=b''):
        "Use an ip port pair to sync"
        return self.httpSync(ip,port,chain)

    def ipPortToUrl(self,ip,port):
        return ("http://"+ip+":"+str(port))
        
    def httpSync(self,url,chain=b''):

        """Gets any updates that an HTTP server might have"""
        if url.endswith("/"):
            pass
        else:
            url+="/"
        
        if chain:
            if not len(chain)==32:
                raise RuntimeError("Invalid key")
        #PUBKEY/newRecords/sinceTime
        r = requests.get(
                url+
                urllib.parse.quote_plus(b64encode(chain or self.pubkey).decode("utf8"))+
                "/newRecords/"+str(self.getModifiedTip(chain)),stream=True)
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
                if not i[b'chain'] in siblings:
                    raise RuntimeError("We don't track that chain")
            try:
                #Internal compressed representation
                c = i[b'chain']
                if c and not len(c)==32:
                    raise ValueError("Invalid len")
                if c==self.pubkey:
                    c=b''
                with self.lock:
                    with self.getConn():
                        #We can compute this ourselfves but we validate if it's given
                        h = None
                        if b'hash' in i:
                            h=i[b'hash']
                        self._insertRecord(i[b"id"],i[b'type'].decode('utf8'),i[b"key"].decode("utf8"),i[b"val"], i[b'ts'], i[b"mod"], i[b"prev"], i[b"prevch"],i[b"sig"],c,url,hash=h)
            except:
                print(traceback.format_exc())
                return inserted
            inserted+=1
        return inserted
            
    def checkSignature(self, id,type,key,h, timestamp,modified, prev,prevchanged, sig,chain=None, value=None):
        
        if chain:
            if notlen(chain)==32:
                raise ValueError("Bad key len")
            if not chain in self.getSiblingChains():
                raise ValueError("Key is for a chain we do not track")
        "Value is optional, it can telll us why the sig failed sometimes"
        d = self.getBytesForSignature(id,type,key,h, timestamp, modified, prev,prevchanged)
        try:
            return libnacl.crypto_sign_verify_detached(sig, d, chain or self.pubkey)
        except:
            if value:
                if not drayer_hash(value)==h:
                    raise RuntimeError("Bad signature likely due to hash mismatch")
            raise RuntimeError("Bad signture, message id was",id, "on chain ", chain)
    
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
        """Return a dict of all sibling chains
            pubkey(bin): entrytimestamp, validstart(0 for never), validend(0 for none).

            This is nowhere near actually tested
        """	
        
        #TODO: actually implement this. It's nowhere near a real thing yet.
        
        c=self.getConn().cursor()
        
        #Note that we don't read from all siblings. The sibling of our sibling is also our sibling.
        #But we are going to handle that with syncing. We need to have a starting place to know
        #what records are valid to be able to look for the rest
        
        c.execute('SELECT id FROM record WHERE key="siblings" and type="drayer" and chain=""')
        #We're always included in our own
        periods = {}
        periods[self.pubkey]={
            b"from": 0,
            b"to":0,
            b"timestamp":0,
            b'pubkey': b''
        }
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
                        
            
    def validateRecord(self,id, chain=b"",allowOtherChains=False, allowMetaOnly=False):
        ##Make sure a record is actually supposed to be there
        x = self.getRecordById(id,chain)

        if not allowOtherChains:
            if not self.isSiblingAtTime(x["chain"],x["modified"]):
                raise RuntimeError("Record belongs to a chain that is/was not the local chain or a sibling when it was made")

        if not isinstance(x['value'],bytes):
            raise TypeError

        h= drayer_hash(x["value"])
        if not h==x["hash"]:
            if x['hash'] == b'':
                if allowMetaOnly:
                    pass
                else:
                    raise RuntimeError("This is a metadata-only record or obsolete record") 
            else:
                raise RuntimeError("Bad Hash")
        
        self.checkSignature(id,x["type"], x["key"], h,x['timestamp'],x["modified"], x["prev"],x["prevchange"], x["signature"],chain, value=x['value'])
        if self._hasRecordBeenDeleted(id,chain):
            raise RuntimeError("Record appears valid but was deleted by a later change")

        if not self.getRecordByModificationTime(x['prevchange'],chain):
            if x['prevchange']:
                raise RuntimeError("Record does not fit onto mchain with back pointer: "+str(x['prevchange']))


    def _idGarbageCollectFor(self,id,prev, chain=b"",fixurl=None):
        ""

        c=self.getConn().cursor()
        c.execute("SELECT * FROM record WHERE id>? AND id<? AND chain=? ORDER BY modified DESC LIMIT 1",(prev,id,chain))
        for i in c:
            if self.privkey:
                n=self.getNextModifiedRecord(i['modified'],chain)['id']
                if n:
                    self._fixPrevChangePointer(n,chain)
            else:
                n=self.getNextModifiedRecord(i['modified'],chain)
                if n:
                    self._requestChainRepair(fixurl, i['prevchange'],n,chain)
            self.getConn().execute("DELETE FROM record WHERE id=? AND chain=?",(id,chain))


    def _requestAllChainRepair(self,url):
        "Try to clean up any obsolete records by getting the chain repair data"
        c = self.getConn().cursor()

        c.excecute("SELECT * FROM record WHERE value=? LIMIT 5",(b'OBSOLETE'))

        for i in c:
            try:
                #You never know, someone could actually put literally the
                #word obsolete there
                if not(i['hash']==drayer_hash(b'OBSOLETE')):
                    self._requestChainRepair(url,i['prevchange'],i,i['chain'])
            except:
                print(traceback.format_exc())
                break
        

        
    def _requestChainRepair(self,url, pdest, oldrecord,chain):
        """We use this when we get something we cannot handle
            without breaking the modified chain
        """
        r = requests.get(
            url+
        
            urllib.parse.quote_plus(b64encode(chain or self.pubkey).decode("utf8"))+
            "/crdr/"+str(pdest)
            ,stream=True)
        r.raise_for_status()
        r=r.raw.read(100*1000*1000)
        
        r = msgpack.unpackb(r)
        

        
        if chain==self.pubkey:
            chain=b''

        h = drayer_hash(r[b'val'])
        if not h==r[b'hash']:
            raise RuntimeError("Not even trying to pretend it's valid")

        self.checkSignature(r[b'id'],r[b'type'].decode("utf8"),r[b'key'].decode("utf8"),r[b'hash'],r[b'ts'], r[b'mod'], r[b'prev'], r[b'prevch'],r[b'sig'],chain,value=r[b'val'])

        if not r[b'prevch']< oldrecord["prevchange"]:
            #We are doing something dangerous, accepting a record
            #With a modified time before the tip. Luckily, when this happens,
            #The back pointer can only move backwards.
            #We can't insert new records into the gap in the modified
            #times. So we always can tell if a version of an old message
            #is good.

            #Interestingly, we might get a record that does not point
            #To the one we asked for. The thing we asked about
            #Might also have been deleted!

            #But nothing will have been inserted in the past

            raise RuntimeError("Impossible pointer value")

        beingReplaced = self.getRecordById(r[b'id'], chain)

        #It is possible, but unlikely that so much has been deleted
        #That a completely new  record points all the way back there.
        #However, in that case it would not be changing history I don't think,
        #Because all that "history" would just be old versions we don't want.
        
        #So this functions should't ever have to handle that.
        #And we raise an exception
        if beingReplaced:
            #We don't allow the pointers to move forwards on old records
            #And the mod tome wouldn't stay the same for anything
            #but a patch
            if not r[b'prevch']< beingReplaced['prevchange']:
                print(beingReplaced['key'])
                raise RuntimeError("Sanity check fail",r[b'prevch'], beingReplaced['prevchange'])

            # I believe there is no reason ever to replace a block
            # with an older block
            if r[b'mod']<beingReplaced['modified']:
                raise RuntimeError("Refusing to replace with older block")


            #Only accept records if they actually fix our chain problem
            if not r[b'prevch']<= pdest:
                raise RuntimeError("New record would not repair chain")

            newp = r[b'prev']
            oldp=beingReplaced['prev']

        else:
            raise RuntimeError("Does not replace existing record")

        
        #Quickly garbage collect any values that this change obsoletes
        if not newp==oldp:
            self._idGarbageCollectFor(oldp,newp,chain)
        #Modified chain GC
        self.getConn().execute("DELETE FROM record WHERE modified>? AND modified<? AND chain=?",(r[b'prevch'],r[b'mod'],chain))


        self.getConn().execute("DELETE FROM record WHERE id=? AND chain=?",(r[b'id'],chain))
        self.getConn().execute("INSERT INTO record VALUES(?,?,?,?,?,?,?,?,?,?,?)",(r[b'id'],r[b'type'].decode("utf8"),r[b'key'].decode("utf8"),r[b'val'],r[b'hash'],r[b'ts'],r[b'mod'],r[b'prev'],r[b'prevch'], r[b'sig'],chain))
        self.validateRecord(r[b'id'],chain)



        
    def _insertRecord(self, id,type,key,value, timestamp,modified, prev,prevchanged, signature, chain=b"", requestURL=None,hash=None):		
        #TODO: Removing peers is super confusing. We'll refuse to add any more to their chains.
        #But if there's already messages will there be race conditions?
        #RequestURL is the URL that we 


        #SQLite isn't strongly typed and this is how we keep corruption out
        if not isinstance(value,bytes):
            raise TypeError()
        if not isinstance(id, int):
            raise TypeError()
        if not isinstance(prev, int):
            raise TypeError()
        if not isinstance(prevchanged, int):
            raise TypeError()
        if not isinstance(modified, int):
            raise TypeError()
        if not isinstance(timestamp, int):
            raise TypeError
        if not isinstance(type, str):
            raise TypeError()
        if not isinstance(key, str):
            raise TypeError()
        if not isinstance(signature, bytes):
            raise TypeError()
            
            
        if not self.isSiblingAtTime(chain, modified):
                raise RuntimeError("Chain must be local chain or a sibling")
        
        if chain==self.pubkey:
            chain=b''

        #The chain we are going to store it in.
        #We may validate against the chain for all but one check,
        #then store it in a different special chain for caching things.
        actualChain = chain
            
        #Most basic test, make sure it's signed correctly
        
        #We don't supply a hash because we check it here anyway
        h= drayer_hash(value)

        #But we can, for better error messages
        if hash:
            if not hash==h:
                raise RuntimeError("Record hash doesn't match data:",value,hash,h)
        self.checkSignature(id,type,key, h,timestamp,modified, prev,prevchanged, signature,chain)
    
        #The thing that the old block that we might be replacing used to point at
        oldPrev = self._getPrev(id,chain)
        

        mtip = self.getModifiedTip(chain)
        doUnknownOnChange = False

        #TODO:Back of chain connections
        if modified<= mtip:
            if modified ==mtip:
                #Just silently return instead of raising an error for inserting the same record
                if self.getRecordByModificationTime(modified)["id"]==id:
                    return
            raise RuntimeError("Modified time cannot be before the tip of the chain")
            
        if not self.getRecordByModificationTime(prevchanged,chain):
            #The new block has to connect SOMEWHERE on the chain but not necessearily 
            #the end, so it can "patch stuff out".

            #Always allow the special case of the thing that's supposed to point at the very start,
            #Imaginary block 0.
            if prevchanged:
                print(self.getModifiedTip(chain))
                #And of course we have the exception for linking to the back
                raise ValueError("New records must connect to an existing value in the mchain, or must connect to the back of the chain. pointer was:"+str(prevchanged))
                

        if not prevchanged==self.getModifiedTip(chain):
            #Actually delete anything it patches out in the mchain
            self.getConn().execute("DELETE FROM record WHERE modified>? ",(prevchanged,))
            #Should do better logic here, but we don't really know what's deleted and what's
            #replaced with something later on I don't think
            doUnknownOnChange = True
        
        

        
        tip = self.getChainTip(chain)
        if not prev ==tip:
            #If the record connects to an existing link in the chain,
            #it's basically forking it, and we should garbage collect everything
            #In between the new record and where it connects

            #I think this is safe to do for all updates to old blocks
            if self.getRecordById(prev,chain):
                if modified<=self.getRecordById(prev,chain)['modified']:
                    raise RuntimeError("Cannot connect to newer with older")
                self._idGarbageCollectFor(id,prev,chain,requestURL)
                #TODO: Put in the real changes
                doUnknownOnChange = True
            elif self.getFirstRecordAfter(id,chain):
                if self.getFirstRecordAfter(id,chain)['prev']<id:
                    raise ValueError("This record was already deleted")
            
            else:
                #In the "Silent patch" we replace with the same
                #But we never replace a record with an older version

                x = self.getRecordById(id,chain)
                ##TODO why is if x needed?
                if x and modified<x['modified']:
                    raise RuntimeError("Cannot replace newer with older")

        oldRecord = self.getRecordById(id, chain)

        #If we are overwriting a record that had something pointing to it,
        #We're going to silently patch what it pointed to, and we aren't going to tell anyone unless they ask.##Also, we can append to the back
        

        #See the readme for why we can get away with this. It's because past state of the modified
        #chain doesn't matter, only the last block. Anyone getting new data gets the new,
        #anyone else doesn't care
        didModify = False
        unpatchedChain = False
        if oldRecord:		
            didModify=True

            #We have to do the chain fix after we actually delete the old record
            #Otherwise we couldn't do DB constraints
            doChainFix=None
            #The record in front that we need to patch
            n = self.getNextModifiedRecord(oldRecord["modified"],chain)
            if n:
                #This is what we think the record before the old record is.
                #Since the record we are replacing won't be there, we need to find
                #What really points at that record(Or the one before it, etc, if it's gone)
                p = oldRecord["prevchange"]	

                #We have the private key, why not do the patch ourselves?
                if self.privkey:
                    def doChainFix():
                        #Explicitly say what to point at
                        self._fixPrevChangePointer(n['id'],chain,p)

                elif requestURL:
                    #We do not have the private key, we need to request more data
                    #to repair the chain so that this new d event from </dev/input/event15>
                    
                    #The oldrecord parameter we pass is thenext record, because the next
                    #record is the one we need to replace to mess with this record.
                    try:
                        def doChainFix():
                            self._requestChainRepair(requestURL, p, n, chain)
                    except:
                        print(traceback.format_exc())
                        logging.exception("Could not get chain repair data")
                        unpatchedChain = True
                else:
                    unpatchedChain=True
            
            if not unpatchedChain:
                self.getConn().execute("DELETE FROM record WHERE id=? AND chain=?",(id,chain))
            else:
                #So much other stuff needs to happen for this to work..
                if False:#self.allowObsolete:
                    self.getConn().execute('INSERT INTO obsolete VALUES (?,?,?)'(id, modified, chain))
                    self.getConn().execute('UPDATE record SET value=? WHERE id=? AND chain=?',(b"", id,chain))
                else:
                    raise RuntimeError("That record would break the chain. To insert it you must supply a URL that can provide repair data, or allow keeping obsolete records.")
            if doChainFix:
                doChainFix()
        self.getConn().execute("INSERT INTO record VALUES(?,?,?,?,?,?,?,?,?,?,?)",(id,type,key,value,h,timestamp,modified,prev,prevchanged, signature,chain))
        self.validateRecord(id,chain)
        try:
            if didModify:
                self.onChange("modify", id, key, chain)
            else:
                self.onChange("add", id, key, chain)

            if doUnknownOnChange:
                self.onChange("unknown",0,0,0)
        except:
            logging.exception("Error in onchange callback")
            print(traceback.format_exc())
        #Now, in a completely different chain, we se if anything has been "patched out" of it.
        if oldPrev:
            if not oldPrev==prev:
                #If we changed prev we need to garbage collect the unreachable node.
                self._hasRecordBeenDeleted(oldPrev,chain)
            
                    
    def __delitem__(self,k):
        self.rawDelete(k,"obj")

    def rawDelete(self,k,t):
        id = self._getIdForKey(k,t)
        with self.lock:
            with self.getConn():
                if not id:
                    raise KeyError(k)
                    
                #The record that references us in the actual chain
                #That we are going to patch to not do that
                n = self._getNextRecord(id)
                
                if not n:
                    if self._hasRecordBeenDeleted(id):
                        raise RuntimeError("Record already deleted")
                    #The block tip cant be GCed so we can't delete it
                    raise RuntimeError("Currently we cannot delete the very most recently added item, but you can add another and try again.")

                p = self._getPrev(id)
                mtip = self.getModifiedTip()
                
                torm = self.getRecordById(id)
                
                #If the record in front of the one we're about to
                #Modify needs to be patched to point at the one behind
                #the one we're deleting, to keep the mchain in order

                #But, it could happen that the one in front of that one,
                #IS the record we want to delete...
                needsPatching = self.getNextModifiedRecord(n["modified"])

                #We don't need to patch it if we're going to delete in first
                if needsPatching and needsPatching['id']==torm['id']:
                    #Instead, we need to patch the one in front of it
                    needsPatching = self.getNextModifiedRecord(needsPatching["modified"])

                #If the record in front of the one we're about to
                #delete may also need patching. Iyt likely will,
                #Unless it's the same as another record we are going to patch.
                needsPatching2 = self.getNextModifiedRecord(torm["modified"])

                #Same record, only patch
                if needsPatching2==needsPatching:
                    needsPatching=None

                #Copy IDs, records may change
                if needsPatching:
                    needsPatching= needsPatching["id"]
                if needsPatching2:
                    needsPatching2=needsPatching2['id']
                #Can't connect to the one we're about to delete either
                if mtip== torm['modified']:
                    x = self.getRecordByModificationTime(torm["prevchange"])
                    if not x:
                        if not torm["prevchange"]==0:
                            #There would be nothing for the record to connect to!
                            raise RuntimeError("Can't remove that record")
                    mtip=torm["prevchange"]
                
                
                #Make a new record for the one right in front of it.
                #insertRecord will handle patching the one in front of *that*?
                t = int(time.time()*1000000)
                sig=self.makeSignature(n["id"],n['type'],n["key"], n["hash"],n['timestamp'],t,p,mtip)
                self._insertRecord(n["id"],n['type'],n["key"],n["value"], n['timestamp'],t,p, mtip,sig,hash=n['hash'])

                if needsPatching:
                    self._fixPrevChangePointer(needsPatching)

                #There may be 2 different records we must patch
                if needsPatching2:
                    self._fixPrevChangePointer(needsPatching2)
        self.broadcastUpdate()
    
            
    def _fixPrevChangePointer(self,id,chain=b'',p=None):
        n=self.getRecordById(id,chain)
        if n==None:
            raise RuntimeError(str(id))
      
        if p is None:
            c = self.getConn().cursor()
            #If the chain is otherwise consistent, the most recent record before this one is the one
            #We should be pointing at
            c.execute("SELECT modified FROM record WHERE modified<? ORDER BY modified DESC",(n["modified"],))
            
            #If there isn't a record before us, we're the first and we 
            #point at zero
            x = c.fetchone()
            if not x:
                x = 0
            else:
                x = x[0]

            if chain==self.pubkey:
                chain=b''
            p=x


        rId=n['id']
        rKey=n['key']
        rHash = n["hash"]
        rMod=n['modified']
        rValue=n['value']
        rPrev=n["prev"]
        rType=n['type']
        rTimestamp = n['timestamp']
        rPrevch = p

        sig=self.makeSignature(rId,rType, rKey, rHash,rTimestamp,rMod,rPrev,rPrevch,chain)
        try:
           # self.getConn().execute("DELETE FROM record WHERE (id=? AND chain=?)",(rId, chain))
            #self.getConn().execute("INSERT INTO record VALUES(?,?,?,?,?,?,?,?,?,?)",(rId,rType,rKey,rValue,rHash,rMod,rPrev, rPrevch,sig,chain))
            self.getConn().execute("UPDATE record SET prevchange=?,signature=? WHERE id=? AND chain=?",(rPrevch,sig, rId,chain))
        
        except:
            print(rId, rKey,rValue,rPrevch)
            raise
        self.validateRecord(rId,chain)



    def insertFile(self,n, f):
        h = {"enc":"gzip","time":os.path.getmtime(f)*10**6}
        i = io.BytesIO()

        gf=gzip.GzipFile(fileobj=i,mode="w")

        with open(f,mode="rb") as fd:
            gf.write(fd.read())
        gf.close()

        h = msgpack.packb(h,use_bin_type=True)
        d=struct.pack("<L", len(h))
        d+=h+i.getvalue()
        self.rawSetItem(n,d,"file")
                
    def __setitem__(self,k, v):
        k,v=self.filterInsert(k,v)
        self.rawSetItem(k,v, "obj")

    def rawSetItem(self,k, v,type, t=None):
        t=t or time.time()*1000000
        with self.lock:
            with self.getConn():
                id = self._getIdForKey(k, type)
                
                if not id:
                    id= self.getChainTip()+1
                    prev = self.getChainTip()
                else:
                    prev= self._getPrev(id)
                    
                mtime = int(time.time()*1000*1000)
                prevMtime = self.getModifiedTip()
                if self.getRecordById(id):
                    if self.getRecordById(id)['modified']==prevMtime:
                        #WE cant connect to the old version of ourselves
                        #so we connect to the record before that and let GC handle it
                        prevMtime = self.getModifiedTipRecord()["prevchange"]

                h = drayer_hash(v)

                sig = self.makeSignature(id,type,k,h,mtime,mtime,prev,prevMtime)

                self._insertRecord(id,type,k,v,mtime, mtime,prev,prevMtime,sig,hash=h)
                self.validateRecord(id)

                self.broadcastUpdate()
        
    def __getitem__(self,k):
        return self.filterGet(self.rawGetItemByKey(k,"obj"))


    def keyExists(self, k, t):
        for i in self._getRecordsForKey(k,t):
            return True
        return False

    def rawGetItemByKey(self,k,t):
        "Gets an item by key. Could be in any chain at all, including the random subchains"
        e = None
        #There could be multiple records for a key.
        #We should have deleted expired ones, but it may be that a no-longer-valid
        #Sibling has recent keys that will fail vaildation, and we want to return to our own verision
        
        #So we try records till we get a valid one
        for i in self._getRecordsForKey(k,t):
            try:
                self.validateRecord(i["id"],i["chain"])
                return i['value']
            except Exception as q:
                e=q
            
        raise e or KeyError(k)
        
    def rawGetRecordByKey(self,k,t):
        "Gets an item by key. Could be in any chain at all"
        for i in self._getRecordsForKey(k,t):
            return i
        return None


    def filterInsert(self,k,v):
        "Preprocess values inserted with the dict insert style"
        return k,msgpack.packb(v,use_bin_type=True)
    
    def filterGet(self,v):
        return msgpack.unpackb(v,raw=False)
        
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
            bthash=drayer_hash(i)
            bthash=drayer_hash(bthash)[:20]
            
            if torrentServer:
                torrentServer.get_peers(bthash)
                torrentServer.announce_peer(bthash, http_port,0,False)
            
        
    def _getIdForKey(self, key,type, chain=b''):
        "Returns the ID of the most recent record with a given key"
        c=self.getConn().cursor()
        c.execute("SELECT id FROM record WHERE key=? AND type=? AND chain=? ORDER BY timestamp desc LIMIT 1",(key,type,chain))
        x = c.fetchone()
        if x:
            return x[0]
            
    def _getRecordsForKey(self, key,type):
        "Returns all records for a key, most recent first"
        c=self.getConn().cursor()
        c.execute("SELECT * FROM record WHERE key=? AND type=? ORDER BY timestamp desc",(key,type))
        return c
            
    def broadcastUpdate(self, addr= (MCAST_GRP,MCAST_PORT),chain=b""):
        
        "Anounce what the tip of the modified chain is, to everyone"		
        if not localDiscovery:
            return
            
        #noServe has one special value Copy that enables this but dis
        if self.noServe==True:
            return
        
        i= self.getModifiedTipRecord(chain)
        if not i:
            return
        chain = chain or self.pubkey
    
    
        sendsock.sendto(self.encUpdate(msgpack.packb({"mtype":"record",
                "hash":i["hash"],
                "key":i["key"],
                "id": i["id"],
                "sig":i["signature"],
                "prev":i["prev"],
                "prevch":i["prevchange"],
                "mod":i["modified"],
                "httpport": http_port,
                "chain":chain
                }),chain),addr)

    def encUpdate(self, data,chain):
        "Encodes a data record or not, depending on if cleartext is on"
        if self.allowCleartext:
            return PLAINTEXT_DRAYERUDP+data
        else:
            return self.encrypt(data)


    #UNUSED
    def encrypt(self,data,chain=b''):
        """Encrypt data using the hash of this streams public key.
           This allows a fair amount of security if attackers don't know about that
           key.
        """
        pass
        # chain = chain or self.pubkey
        # h1=libnacl.crypto_generichash(chain)
        # h2=libnacl.crypto_generichash(chain)
        # x=os.urandom(libnacl.crypto_secretbox_NONCEBYTES)
        # return  h2+x+libnacl.crypto_secretbox(data,x,h1)


    def _hasRecordBeenDeleted(self,id,chain=b""):
        "Returns True, and also deletes the record for real, if it should be garbage collected because its unreachable"

        x =self.getRecordById(id,chain)
        #It doesn't exist, so apperantly yes!
        if not x:
            return True

        d=False
        if self.getFirstRecordAfter(id,chain):
            if self.getFirstRecordAfter(id,chain)['prev']<id:
                d=True

        #Check if it's been patched out of the mchain
        nextmod =self.getFirstModifiedRecordAfter(x['modified'],chain)
        if nextmod:
            if nextmod['prevchange']<  x['modified']:
                #This condition means it HAS been deleted
                d=True

        if d:
            key = x['key']
            #Delete the record for real, so it doesn't trouble us anymore
            self.getConn().execute("DELETE FROM record WHERE id=? AND chain=?",(id,chain))
            #No onchange, this is an odd state that should't happen
            return True
        return False

        
    def _getPrev(self,id,chain=b''):
        "Returns the id of the previous block in the chain"
        c=self.getConn().cursor()
        c.execute("SELECT prev FROM record WHERE id=? AND chain=? ORDER BY modified desc",(id,chain))
        x= c.fetchone()
        if x:
            return x[0]
        return 0
        
    def _getNextRecord(self,id,chain=b''):
        "Returns the previous block in the chain"
        c=self.getConn().cursor()
        c.execute("SELECT * FROM record WHERE prev=? AND chain=? ORDER BY modified desc",(id,chain))
        x= c.fetchone()
        if x:
            return x
        return 0	




    def getChainRepair(self,t,chain=b''):
        """Get the thing that points at t, but if t is gone, get whatever points at the existing block that comes before t
            The actual logic is to find the earliest thing that points at t or before 
        
        """
        if chain==self.pubkey:
            chain=b''
        c=self.getConn().cursor()
        c.execute("SELECT * FROM record WHERE prevchange<=? AND chain=? ORDER BY prevchange DESC",(t,chain))
        x= c.fetchone()
        if x:
            return x
        return None

    def getNextModifiedRecord(self,t,chain=b''):
        "Returns the next block in the modified chain"
        if chain==self.pubkey:
            chain=b''
        c=self.getConn().cursor()
        c.execute("SELECT * FROM record WHERE prevchange=? AND chain=? ORDER BY modified DESC",(t,chain))
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
        c.execute("SELECT * FROM record WHERE id=? AND chain=? ORDER BY modified DESC",(id,chain))
        return c.fetchone()

    def getFirstRecordAfter(self,id,chain=b''):
        c=self.getConn().cursor()
        c.execute("SELECT * FROM record WHERE id>? AND chain=? ORDER BY id ASC,modified DESC",(id,chain))
        return c.fetchone()		

    def getFirstModifiedRecordAfter(self,m,chain=b''):
        c=self.getConn().cursor()
        c.execute("SELECT * FROM record WHERE modified>? AND chain=? ORDER BY modified ASC",(m,chain))

        return c.fetchone()			

    def getChainTip(self,chain=b''):			
        "Gets the record at the tip of the record chain"
        c=self.getConn().cursor()
        c.execute("SELECT id FROM record WHERE chain=? ORDER BY id DESC, modified DESC",(chain,))
    
        x=c.fetchone()
        if not x==None:
            return x[0]
        return 0
        
    def getChainBackPointer(self,chain=b""):
        "Gets whatever the back record is pointing to. If it's not 0, we don't have full history"
        c=self.getConn().cursor()
        c.execute("SELECT prev FROM record WHERE chain=? ORDER BY id ASC, modified DESC",(chain,))
        x=c.fetchone()
        if not x==None:
            return x[0]
        return 0
        
    def getRecordsSince(self,t,chain=b''):
        "Gets the cursor that can iterate over a certain number of records. Returns records for all chains"
        if chain ==self.pubkey:
            chain = b''
        c=self.getConn().cursor()
        c.execute("SELECT * FROM record WHERE modified>? AND chain=? ORDER BY modified ASC",(t,chain))
        return c


    def getModifiedTip(self,chain=b""):
        "Get the most recently modified records's modified time"
        c=self.getConn().cursor()
        c.execute("SELECT modified FROM record WHERE chain=? ORDER BY modified DESC",(chain,))
        x=c.fetchone()
        if x:
            return x[0]
        return 0
        
    def getModifiedTipRecord(self,chain=b""):
        "Get the most recently modified records's modified time"
        c=self.getConn().cursor()
        c.execute("SELECT * FROM record WHERE chain=? ORDER BY modified DESC",(chain,))
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
        with self.lock:
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
            if not b[:4]== PLAINTEXT_DRAYERUDP:
                continue
            try:
                d=msgpack.unpackb(b[4:])				
                if d[b"mtype"] == b"getRecordsSince":
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
                            
                if d[b"mtype"] == b"record":
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

def startServer(port=None):
    global http_port
    http_port=_startServer(port)
    return http_port

def _startServer(port=None):
    global http_port
    
    if port:
        http_port=port

    cherrypy.tree.mount(DrayerWebServer(), '/',{})
    
    for i in range(0,40):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", http_port))
            s.close()
            cherrypy.config.update({'server.socket_port': http_port,'server.socket_host' : '0.0.0.0'})
            cherrypy.engine.start()
            break
        except:
            print(traceback.format_exc())
            if i==39:
                raise
            if port:
                #Can't override manual selected por
                raise
            #Trying random ports till we find a good one
            http_port = random.randint(8000, 48000)
    return http_port
