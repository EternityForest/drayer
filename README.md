# Drayer
Like Scuttlebutt, but fully mutable and implemented as a python library.

Drayer is a protocol for distributed streams that act like Twitter feeds.
You can add, edit, or delete records, without keeping around old data like similar protocols.

You can start downloading the chain at any point, access individual records withouot downloading everything,
get metadata-only copies of records, and mirror the most recent N records without mirroring everything.

Streams are stored as sqlite files that have an embedded public key. A stream is writable if there's a corresponding
private key(As in "foo.stream" and "foo.stream.privatekey").  As with blockchain and scuttlebutt, only one person can
write to a stream, because each change still references the last change.


Absolutely everything subject to change(Just like our fully mutable streams!). Project is a few days old and
is not even pre-alpha.


## Using it!

Dependancies:
Python3, upnpclient(unused right now but will be needed), requests, cherrypy,libnacl

All are available with pip3 install.

Making a new stream:
```python
	import drayer
	#Starts an actual CherryPy server process
	drayer.startServer()
	drayer.startLocalDiscovery()

	#If it doesn't exist, it is created, along with a new keypair
	d = drayer.DrayerStream("fooo.stream")
	print(d.getAttr("PublicKey"))
	
	#Right now they only support dict-like access
	d["foo3"] = b"testing"
	d["foo"] = b"testing3"
	print(d["foo"])
```

Cloning a stream:
```
import drayer, time

#replace the pubkey with the key you got from the original stream
#Since we are asking for a specific pubkey and we don't have the private key
#It knows we're trying to clone it.
drayer.startLocalDiscovery()
d2 = drayer.DrayerStream("foooClone.stream", "1gqqI9XK7Lnch1F+qnV+1o6oq91KsXN38hKwQ50qdmw=")
time.sleep(2)
d2.sync()
time.sleep(2)
print(d2["foo3"])
```

## Top level functions

### startBittorent()
Start a Mainline DHT node. Preferrably, don't use this for nodes that will only be briefly online.

Instead, it's best to run an always-on server with local discovery enabled.

## The DrayerStream

### setPrimaryServers(s):
Input must be list of dicts with the key type="html" and "url" = the HTTP sync url for that server.

Drayer will use those and ignore other servers if it can. Note that the list of primary servers is stored
as a record directly in the chain, so all nodes that mirror it will get the same list.



### announceDHT():
Makes the stream findable via MainlineDHT. Don't use this unless you plan to have the node online for at least a few hours.

Requires that drayer.startServer() and drayer.startBittorent() be called.


## How it works

Records are a part of two separate chains with different ordering. They have a ID chain, where blocks reference the previous
block by ID. Any block except the "tip" must be referenced by a later block or it will be garbage collected.

Changing the contents of a block does not change it's ID, so older blocks can be edited freely, and deleted by changing the block in
front to point to the block behind, causing garbage collection of the floating block.

In addition, there is a one-block long Modified Chain. Every time you change a block, you update it's "prevchanged" pointer
to point at the most recently modified block before it. EVery new change must point at the previous change, but the chain is
only one block long, so we can freely "shuffle" old blocks to the new "front" of that chain.


This ensures that we handle blocks in-order with no "hidden block problem" where a newer block arrives before an older block, "hiding"
one in the middle from algorithms that use simple "DO you have anything newer than X" searches.

Of course, the whole point is to be able to mirror a chain and have other people trust that the mirror is the same as the original.

To that end, every block is digitally signed, and the inclusion of the modified date means you can use the system as a simple
unsorted collection of records that can be mirrored individually.

You will not know if a block has been deleted if you don't download a more complete chain to see if there's still
references, but this doesn't matter in some use cases.



### Missing Block Problem, and Solution

There's just a few problems with all that though, and that's mainly the fact that the next block in the modified
chain could get deleted, and we might have no idea, and we'd wait forever to find a block that doesn't exist.


However this isn't actually much of an issue, with a few small modifications.

Suppose the source has blocks 1,2,and 3(In order of the modified chain), and a mirror has an copy.

You have block 1. The source changes block 2. In the modified chain, block 2 becomes block 4.

Block 3 is now invalid, because the date that 3 points to no longer exists. 

To solve this, It changes the modified date of 3 to point to 1, but does not change the modification date of 3.



If you sync with the mirror, you will get block the old block 2, then block 3, then presumably eventually block 4, which will overwrite
2, and nobody will care about the previous stuff, because the chain is only one block.

If you sync with the original, you will get block 3(Silently patched to point at 1), and you will never know that 2 existed.

As well you should not, because it's no longer relevant.


If you sync with the mirror up to block 2, and then try to sync with the server, you will get block 2, but then the server will
give you block 3, which points at one. To make this work, we allow new blocks to connect to existing parts of the chain, "cutting them out".

In this way we can edit things without changing the modified time, because we don't actually need to propagate that change.
Everything just goes on as usual even if the chain is broken, so long as the front part of the chain is valid.

### Chain repair data request

Of course, now we have a new problem. In this scenario node A is at block four, B is at block three, and C is at block five.

Node B will sync correctly, ignoring the corruption to its old modified chain.

Node C however can no longer sync with B, because it doesn't have blocks and so can't ignore the modified chain like B could.

Normally, B could just patch it's own chain, fixing things when it notices that
it would be broken.

However, we use digital signatures, and only A can create them.

So, we do another hack. When we someone gives us a block that would change an existing block(Thus removing it from it's spot in the modified chain), we must ask the node
that sent it to us for the replacement block just in front.

It is not possible for them to know without us asking, because they have already deleted
the informating that would tell them the chain has ever been touched.

We then use this new block to perform the "silient update", and carry on.

This should ensure that every block either points to a previous entry in the mod chain,
or to zero, and we only care that each mirror's modified chain is consistent with itself.

### Replay attacks

We do not want those on our chains. So we do a bit of validation on these silent updates.  See code for details, If the new block points at the same thing as the old, it 
the new block must be newer. Otherwise the pointer must point to something before the old pointer.



## Order Mismatching, and solution

We can see that we have another problem now. The ID and the modified chains can be in
a totally different order! When we transmit blocks, we send in modified order, so recievers can get blocks that don't fit in the ID chain!!

We solve this by allowing gaps in the ID chain. Our new GC criteria is that a block gets deleted if the next block after it points to something before it.

Eventually, the modified chain ensures that we get all blocks, letting us know what's been deleted. We can't miss a block.

## Record Structure:
     
 We use libsodium's `crypto_sign_detached` to compute signatures(Which uses curve25519), and we use
 crypto_generichash for hashing(That's blake2b). 
 
 All timestamps are in microseconds since the UNIX epoch as 64 bits.
 
 `prev` points to the prev record by it's ID, `prevchanged`	points by modified date.

 The signature for a record is computed on the following byte sequence, defined by this
 python code:
 
 `struct.pack("<QqqqL", id,modified,prev, prevchanged,len(key))+key.encode("utf8")+h`
 
 Where h is the unkeyed hash of the value of that key. The indirection has several useful
 properties.


## SQlite Storage
The actual records are stored in the following table:
`CREATE TABLE IF NOT EXISTS record (id integer primary key, key text, value blob, hash blob, modified integer, prev integer, prevchange integer, signature blob,chain blob);`

The chain entry is normally blank, but we have native support for "sibling chains", so we can store OTHER chains in here that are considered "included"
when we ask for results. These other chains should sync just like the main chain although we can only add to the main chain.

The basic "attributes", misc data we store in the file, is kept in:
`CREATE TABLE IF NOT EXISTS attr (key text, value text);`

The public key is kept base64 encoded in the attribute "PublicKey". Attributes are not synced, they're just for local storage.

The private key, for writable records, is kept base64 encoded in STREAM_FN+".privatekey"


## Discovery and Transport.

Drayer doesn't try to ensure privacy at all. Think of it like IPFS or Bitcoin, where pseudonyms are public and encyrption is
all up to you.  The only cryptograpy is signatures and hashes, which means you can run it over HAM radio if you want.  You
can easily encrypt messages before posting with libsodium if you want.

Most communication happens over plain HTTP. Everything is digitally signed so there's no way to tamper records even on
untrusted networks. HTTPS could easily be used, but the reference implementation doesn't for now.

Using HTTP means that a future javascript implementation is possible.



### HTTP Protocol

Drayer servers are identified by a URL, and all these commands should be interpreted as the part of the URL that comes after
the mount point,(If mounted at /, then you would say example.com/newRecords).

#### newRecords/<STREAM_PUBKEY_B64>/<TIMESTAMP>

Returns a messagepack endcoded list of records, where each is a dict with the following keys. B64 encoding is not used.

Records should be sorted oldest-first, and the total size of the response shouldn't be too big(Don't pile on all records).
Only records modified after thre timestamp should be sent.

Clients should repeat the request if many records were sent(>100), to make sure there's not more of them that didn't fit.

##### id
##### hash
##### key
##### val
##### mod
##### prev
##### sig
##### chain
Which chain the record belongs to (Binary pubkey). If this is blank, it is the "primary chain", the actual one being requested.
However it can also be a "sibling chain", considered "merged" with this chain, to simulate the abilty to have multiple writers for one
stream.

It is acceptable to omit the val key for large files, to only transfer metadata.


### DrayerUDP
Drayer has several means of discovery. The primary one being DrayerUDP, a LAN based multicasting protocol that uses msgpack.


All multicast traffic should use group: 224.7.130.8 and port: 15723

Traffic should be sent FROM a randomly selected port with the mcast port only for listening.

## Extra features

Blocks have a non-unique string name field, so the use of a stream as a dict-like object is natively supported.
