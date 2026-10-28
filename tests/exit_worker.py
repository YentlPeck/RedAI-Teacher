import json, sys
import test_exhaustive_exits as E
print(json.dumps(E.audit(shard=int(sys.argv[2]), shards=int(sys.argv[3]))))
