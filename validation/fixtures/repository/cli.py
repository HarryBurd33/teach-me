from parser import parse

def main():
    record = parse(input("name,count> "))
    print(f"{record.name}: {record.count}")

if __name__ == "__main__":
    main()
