import drayer, time

#drayer.startBittorent()
drayer.startLocalDiscovery()
#time.sleep(15)

d2 = drayer.DrayerStream("foooClone.stream", "0dolzoNQCyXJ6mUBD0BNQwK/WjUF1xM00f6nFouiTMM=")
time.sleep(2)
d2.sync()
time.sleep(2)
d2.sync()

time.sleep(2)
print("sync")
d2.sync()
print(d2["foo7"])

time.sleep(90)
d2.sync()
