import gzip, base64, textwrap
raw = open('Gemma/train/data/localization_traj_train.jsonl', 'rb').read()
blob = base64.b64encode(gzip.compress(raw, 9)).decode('ascii')
print(f"raw={len(raw)} b64gz={len(blob)}")
# write the blob wrapped to 100-char lines into a python-literal snippet
with open('Gemma/_data_blob.txt', 'w', encoding='utf-8') as f:
    f.write('_DATA_B64GZ = (\n')
    for line in textwrap.wrap(blob, 100):
        f.write(f'    "{line}"\n')
    f.write(')\n')
print("wrote Gemma/_data_blob.txt")
