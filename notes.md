, "hiding"
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
