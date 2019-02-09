import drayer, time

d2 = drayer.DrayerStream("foooClone.stream", "Ag5SCQ6CYBCqZKlpDQD/sBb/2L8voXIVPn5p391Su1o=")
time.sleep(2)
d2.sync()
time.sleep(2)
print(d2["foo3"])
