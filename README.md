# Drayer
Like Scuttlebutt, but fully mutable and implemented as a python library.

Drayer is a protocol for distributed streams that act like Twitter feeds.
You can add, edit, or delete records, without keeping around old data like similar protocols.

You can start downloading the chain at any point, access individual records withouot downloading everything,
get metadata-only copies of records, and mirror the most recent N records without mirroring everything.

Streams are stored as sqlite files that have an embedded public key. A stream is writable if there's a corresponding
private key(As in "foo.stream" and "foo.stream.privatekey").  As with blockchain and scuttlebutt, only one person can
write to a stream, because each change still references the last change.

All records have embedded type information as a db column, allowing fast application level queries by type.


Absolutely everything subject to change(Just like our fully mutable streams!). Project is a few days old and
is not even pre-alpha.

## Drake

Drake is both a GUI app and an application layer. Note that at the moment,
the GUI apps here work but ARE NOT PRIVATE if you use them while connected to untrusted
networks.

Qdrake lets you make publicSocialPosts, clone streams, read posts in cloned streams, sync streams, add files to the stream, and with `qrcode` installed lets you show a QR code for a mibile browser on the same LAN to view an `index.html` included in the stream.



### Why it isn't private

They enable local network serving of any streams you load. 

There may be an option to disable this, but in general
the primary design intent of Drayer is as an unencrypted data structure
with encryption provided by either the transport layer or the application.

You should not put anything private at all into a Drayer stream, unless you
either encrypt it yoursel of only use it with apps that do not share things publically.

This might change, and it would not be too hard to create an optional encrypted
version of the UDP discovery that is unreadable by anyone who doesn't already
know a stream's PK.

For now there are many used for fully authenticated cleartext communication, and the
privacy is no worse than many, many other P2P protocols that share your IP and what you're downloading with the world.

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

Records are a part of two separate chains with different ordering, in a data structure
that in theory prevents the hidden node problem, where a newer record arrives before an older record, and we don't know we're missing blocks.

One chain is ordered by a fixed ID, the other is ordered by modification time, with the
exception that we are allowed to change the pointer in the modification time chain without changing the timestamp of that block, so as to repair the chain after moving an
entry,

Deletion is handled via garbage collection in either chain. Most operations should be O(1), making the scaling limits more about the implementation and the database.

See theory.md and notes.md if you want to know more.

## Record Structure:
     
 We use libsodium's `crypto_sign_detached` to compute signatures(Which uses curve25519), and we use
 crypto_generichash for hashing(That's blake2b). 
 
 All timestamps are in microseconds since the UNIX epoch as 64 bits.
 
 `prev` points to the prev record by it's ID, `prevchanged`	points by modified date.

 The signature for a record is computed on the following byte sequence, defined by this
 python code:
 
 `return struct.pack("<Qqqqq", id,timestamp,modified,prev, prevchanged)+drayer_hash(key.encode("utf8"))+h+drayer_hash(type.encode("utf8"))`
 
 Where h is the unkeyed hash of the value of that key. The indirection has several useful
 properties.


## SQlite Storage
The actual records are stored in the following table:
`CREATE TABLE IF NOT EXISTS record (id integer, type text, key text, value blob, hash blob,timestamp integer,  modified integer, prev integer, prevchange integer, signature blob,chain blob);`

The chain entry is normally blank, but we have native support for "sibling chains", so we can store OTHER chains in here that are considered "included"
when we ask for results. These other chains should sync just like the main chain although we can only add to the main chain.

We have both a "timestamp" and a "modified time". The difference is that the modified time is for the record itself, and may change for reasons that have nothing to do with the data itself, and so cannot be used by applications.

The timestamp is purely apaplication level, and has no specific protocol level requirements. It is included mostly to allow conflict resolution between multiple chains.

However, the "file" datatype standard still uses a separate timestamp. This is for compaitibility with .zip files, which encode the actual modified date of the source file,and for conflict resolution it is helpful to know both the time the actual file changed, and the time it was entered into a stream. This allows moving to an older file, while stil allowing multi-stream conflict resolution.

Any application where timestamps can move backwards, should use embedded timesetamps in the data instead, otherwise conflict resolution may reject stamps that have moved backwards, when the application uses multiple chains.




The basic "attributes", misc data we store in the file, is kept in:
`CREATE TABLE IF NOT EXISTS attr (key text, value text);`

The public key is kept base64 encoded in the attribute "PublicKey". Attributes are not synced, they're just for local storage.

The private key, for writable records, is kept base64 encoded in STREAM_FN+".privatekey"


## Including files in a stream

We define a special type, "file", for storing files in the stream as you might in a .zip
file. File data starts with a 4 byte header length and a messagepack header.

As a higher-level application spec, the messagepack headers use the new separate string and bin types unlike lower level Drayer protocol APIs.

The header must have 2 keys, enc, a string representing the encoding(must be "gzip" for now), and "time", the time in microseconds of the file's real modification date(Not it's containing stream record).

The rest of the entry must simply be the compressed file data.


The reason that gzip was chosen is that python has native support for it, and so do browsers.


## Discovery and Transport.

Drayer doesn't try to ensure privacy at all. Think of it like IPFS or Bitcoin, where pseudonyms are public and encyrption is
all up to you.  The only cryptograpy is signatures and hashes, which means you can run it over HAM radio if you want.  You
can easily encrypt messages before posting with libsodium if you want.

Most communication happens over plain HTTP. Everything is digitally signed so there's no way to tamper records even on
untrusted networks. HTTPS could easily be used, but the reference implementation doesn't for now.

Using HTTP means that a future javascript implementation is possible.

## Primary Servers

Streams can have embedded lists of primary servers, so you know where to go for updates.

This is stored in key:type primaryServers:drayer, and is a msgpack liat of dicts having a type and url field(type must be "http" for now). Note that as this is somewhat of a higher level extension, we use msgpack's separate bin and string types, as everything
except the core should.


### HTTP Protocol

Drayer servers are identified by a URL, and all these commands should be interpreted as the part of the URL that comes after
the mount point,(If mounted at /, then you would say example.com/pubkey/newRecords).

Note that these all start with the publlic key of the stream you want to acess.



#### <STREAM_PUBKEY_B64>/newestRecordsJSON/type

Gets up to 250 of the most recently created records of a certain type, as a list of [key,id] lists, in JSON.

the url request params after and before, may be used
to limit the results to a certain set of IDs. Both limits are not inclusive.



#### <STREAM_PUBKEY_B64>/listRecordsJSON/type

Gets up to 250 of the most recently modified records of a certain type, as a list of [key,time] lists, in JSON.

the url request params after and before, may be used
to limit the results to a certain set of times. Both limits are not inclusive.

All times are in microseconds since the UNIX epoch.


#### <STREAM_PUBKEY_B64>/webAccess/**

Here ** denotes a file path. The file path will be used to look up the
key in the stream that has the type "file", and it will be decoded(but not decompressed),
and the raw data sent to the client with the appropriate content encoding variable set.

This lets any node act as a simple static webserver.

#### <STREAM_PUBKEY_B64>/newRecords/<TIMESTAMP>

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
