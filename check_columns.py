from pybaseball import playerid_lookup

results = playerid_lookup("betts", "mookie")
print("Kolom yang tersedia:")
print(results.columns.tolist())
print("\nData:")
print(results)