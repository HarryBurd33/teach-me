from model import Record

def parse(line):
    name, count = line.split(",")
    return Record(name.strip(), int(count))
