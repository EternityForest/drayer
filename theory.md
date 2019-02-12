
# Theory


We have a collection of records, published by one source, that we want to make redistributable, while ensuring that nobody can forge messages.

We also want messages to be editable and deletable, without any leftover trace of the old message.


Every block is a member of two separate linked lists that can be in different orders. One is ordered by the creation of the blocks, and one is ordered by their modification time.

We call these the IDChain and the mchain.


Blocks are almost always transmitted in order of modification. The mchain is used to detect deletion, using the automatic garbage collection principle.

We do not keep old state for any block. When we update a block, it is a true mutable update, and when we delete a block, we do not leave any marker that it was there.

Updating a block leaves it where it is in the IDChain but moves it to the front of the Mchain.

No block may exist if the block with the next-highest id has a prev pointer that points
to something before it. If that ever happens, it means that a block's prev pointer has changed, and we should garbage collect the "skipped over" block.


No new block with a lower ID than an existing block may be created. No block with a lower modification time than the most recent may be created.

No block update may be processed in any order except exactly the order they were made in, except for the fact that we can skip anything that no longer exists, and we can "patch" existing blocks so that their prevchange pointer points to an earlier block.


To ensure this, every blocks prevch pointer must point at a block we have, or else at 0. If it "skips past" any blocks, it indicates those blocks should not exist anymore. No block skips past anything when it is created, so if it ever skips anything we know the skipped blocks were deleted.



On any particular machine, Modification times and prevchange pointers most form an unbroken linked list, going as far back as the segment of the chain you have.

We do not expect the modification timestamp chain(the mchain) to be globally the same until everything is up to date.

This means that when a block is moved, the block in front must be "patched" to point to the one behind it, or to zero.

We do not change the modification timestamp for this patched block. There is no risk of this change getting "lost" because nodes that need it will specifically ask for it. We don't need to keep track of the fact that a patch happened.


If we get a block that modifies an old block, it takes that block out of it's old place, and we cannot patch the one in front because we don't have the private key, we must ask the node that gave us the block for the "chain repair data" for the block ahead, which is whatever block comes next after the block being moved's "old place".

They will always have it if they are a full mirror, or they could not have had the new block, because they would not have accepted a block that corrupts their mchain.

This property means full mirrors are unlikely to be able to sync to partial mirrors that will not have these older blocks. However, partial mirrors can always sync to other partial mirrors with the same or longer history.


Newly created blocks form a linked list of id's and prev pointers. However we allow gaps in this chain(We have to, because we will get them out of order). We use the overshoot-based metric to decide if a block has been deleted.

An advantage of the overshoot metric is that deleting a block never causes deletion of another block, so we can safely remove old blocks in partial mirrors.

To delete a block, we modify the block in front(We cannot delete the most recent in the ID chain), to point to the block behind it. This requires the "silent patch" to the prevchange pointer of the block ahead of the one being modified to point to the one before the one being deleted, thus cutting them out of both chains.




The reason we must have two chains is that if we had only the modified chain, we could not delete things.

A block's prevchange pointer declares that there is no valid data between it and where it points, and we cannot insert blocks into the modified chain except at the front(Although we can delete them).

Without this second chain we could only delete large the most recent N entries, not arbitrary elements in the list.


We do support deletion using only the mchain, that is how we are able to support modifying and deleting the most recently added or modified block.

Although we cannot delete the last block using the IDChain alone, because it is the anchor, we can move the second block in the ID chain to the front of the Mchain, becoming the new ID tip and deleting the unwanted block.




In practice, a full mirror node can choose to accept "floating" blocks that would otherwise break the chain, by holding them in a separate "Floating block store" with looser validation, and don't "accept" them until we have the proper chain repair data.

To simplify the algorithm, we simply discard these blocks when a block in the "real" chain moves past.

We can in many cases reshare these blocks, although we will not be able to provide the chain repair data, and the blocks will remain floating.  This will not cause a problem until a node that is not caught up past any missing blocks wants to sync.

We can even stack regular blocks on top of floating blocks, and promote floating blocks to regular blocks.


A floating block is exactly the same as a regular block, the only difference is that it causes older blocks in the chain to become corrupted until repaired, but it has no effect on the chain before the older block it replaces.
We have a collection of records, published by one source, that we want to make redistributable, while ensuring that nobody can forge messages.

We also want messages to be editable and deletable, without any leftover trace of the old message.


Every block is a member of two separate linked lists that can be in different orders. One is ordered by the creation of the blocks, and one is ordered by their modification time.

We call these the IDChain and the mchain.


Blocks are almost always transmitted in order of modification. The mchain is used to detect deletion, using the automatic garbage collection principle.

We do not keep old state for any block. When we update a block, it is a true mutable update, and when we delete a block, we do not leave any marker that it was there.

Updating a block leaves it where it is in the IDChain but moves it to the front of the Mchain.

No block may exist if the block with the next-highest id has a prev pointer that points
to something before it. If that ever happens, it means that a block's prev pointer has changed, and we should garbage collect the "skipped over" block.


No new block with a lower ID than an existing block may be created. No block with a lower modification time than the most recent may be created.

No block update may be processed in any order except exactly the order they were made in, except for the fact that we can skip anything that no longer exists, and we can "patch" existing blocks so that their prevchange pointer points to an earlier block.


To ensure this, every blocks prevch pointer must point at a block we have, or else at 0. If it "skips past" any blocks, it indicates those blocks should not exist anymore. No block skips past anything when it is created, so if it ever skips anything we know the skipped blocks were deleted.



On any particular machine, Modification times and prevchange pointers most form an unbroken linked list, going as far back as the segment of the chain you have.

We do not expect the modification timestamp chain(the mchain) to be globally the same until everything is up to date.

This means that when a block is moved, the block in front must be "patched" to point to the one behind it, or to zero.

We do not change the modification timestamp for this patched block. There is no risk of this change getting "lost" because nodes that need it will specifically ask for it. We don't need to keep track of the fact that a patch happened.


If we get a block that modifies an old block, it takes that block out of it's old place, and we cannot patch the one in front because we don't have the private key, we must ask the node that gave us the block for the "chain repair data" for the block ahead, which is whatever block comes next after the block being moved's "old place".

They will always have it if they are a full mirror, or they could not have had the new block, because they would not have accepted a block that corrupts their mchain.

This property means full mirrors are unlikely to be able to sync to partial mirrors that will not have these older blocks. However, partial mirrors can always sync to other partial mirrors with the same or longer history.


Newly created blocks form a linked list of id's and prev pointers. However we allow gaps in this chain(We have to, because we will get them out of order). We use the overshoot-based metric to decide if a block has been deleted.

An advantage of the overshoot metric is that deleting a block never causes deletion of another block, so we can safely remove old blocks in partial mirrors.

To delete a block, we modify the block in front(We cannot delete the most recent in the ID chain), to point to the block behind it. This requires the "silent patch" to the prevchange pointer of the block ahead of the one being modified to point to the one before the one being deleted, thus cutting them out of both chains.




The reason we must have two chains is that if we had only the modified chain, we could not delete things.

A block's prevchange pointer declares that there is no valid data between it and where it points, and we cannot insert blocks into the modified chain except at the front(Although we can delete them).

Without this second chain we could only delete large the most recent N entries, not arbitrary elements in the list.


We do support deletion using only the mchain, that is how we are able to support modifying and deleting the most recently added or modified block.

Although we cannot delete the last block using the IDChain alone, because it is the anchor, we can move the second block in the ID chain to the front of the Mchain, becoming the new ID tip and deleting the unwanted block.




In practice, a full mirror node can choose to accept "floating" blocks that would otherwise break the chain, by holding them in a separate "Floating block store" with looser validation, and don't "accept" them until we have the proper chain repair data.

To simplify the algorithm, we simply discard these blocks when a block in the "real" chain moves past.

We can in many cases reshare these blocks, although we will not be able to provide the chain repair data, and the blocks will remain floating.  This will not cause a problem until a node that is not caught up past any missing blocks wants to sync.

We can even stack regular blocks on top of floating blocks, and promote floating blocks to regular blocks.


A floating block is exactly the same as a regular block, the only difference is that it causes older blocks in the chain to become corrupted until repaired, but it has no effect on the chain before the older block it replaces.


To ensure that all nodes can still sync with us, even in the presence of floating blocks, we can cache the old deleted blocks that they replace. We can serve the outdated data to new peers, which will quickly be replaced (The nodes will presumably move the old blocks to their own cache), until such a time as they get the repair data.

This causes nodes to receive outdated data, but it is no different than the outdated data they would get by syncing with an outdated mirror.

It does however, mean that nodes may see a different time series, as one node may see an old record get replaced by a new record, and another may not see the old record at all.

This issue also happens when one node syncs  incrementally and sees changes as they happen, and another syncs all at once and does not see files that are already gone.


In the case that multiple nodes somehow make conflicting blocks, the result is undefined, and may result in corruption that cannot be automatically recovered from, but may be manually recovered by garbage collecting all corrupted records.


To ensure that all nodes can still sync with us, even in the presence of floating blocks, we can cache the old deleted blocks that they replace. We can serve the outdated data to new peers, which will quickly be replaced (The nodes will presumably move the old blocks to their own cache), until such a time as they get the repair data.

This causes nodes to receive outdated data, but it is no different than the outdated data they would get by syncing with an outdated mirror.

It does however, mean that nodes may see a different time series, as one node may see an old record get replaced by a new record, and another may not see the old record at all.

This issue also happens when one node syncs  incrementally and sees changes as they happen, and another syncs all at once and does not see files that are already gone.


In the case that multiple nodes somehow make conflicting blocks, the result is undefined, and may result in corruption that cannot be automatically recovered from, but may be manually recovered by garbage collecting all corrupted records.