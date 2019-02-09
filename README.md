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

Making a new stream:
```python
	import drayer
	#Starts an actual CherryPy server process
	startServer()
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
d2 = drayer.DrayerStream("foooClone.stream", "1gqqI9XK7Lnch1F+qnV+1o6oq91KsXN38hKwQ50qdmw=")
time.sleep(2)
d2.sync()
time.sleep(2)
print(d2["foo3"])
```


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
Drayer has several means of discovery. The primary one being DrayerUDP, a LAN based multicasting protocol that allows
nodes to ask for any new records in nearby blocks, and to inform nearby nodes about changes to blocks.

This protocol is very simple, consting of newline separated text, with two commands at the moment.

To announce a record:
`
record
<b64encoded pubkey of stream>
<ascii base10 modified timestamp of record>
<port number of HTTP server to get said record>
`
The server should have the DrayerHTTP interface mounted at / on it's tree.


To look for new records in a chain:
`
getRecordsSince
<b64encoded pubkey of stream>
<ascii base10 modified timestamp of the tip of your local modified chain>
`
Everyone with records newer than this should unicast you back a record packet representing the latest.

All multicast traffic should use group: 224.7.130.8 and port: 15723

Traffic should be sent FROM a randomly selected port with the mcast port only for listening.

## Extra features

Blocks have a non-unique string name field, so the use of a stream as a dict-like object is natively supported.
