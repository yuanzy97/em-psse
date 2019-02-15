from em_psse import *

import networkx as nx

import argparse
import logging

logger = logging.getLogger('em.parse_raw')

parser = argparse.ArgumentParser(description='Parse PSSE Files')

parser.add_argument('--input',
	help="Input RAW file")
parser.add_argument(
	'-d', '--debug',
	help="Print lots of debugging statements",
	action="store_const", dest="loglevel", const=logging.DEBUG,
	default=logging.WARNING,
)
parser.add_argument(
	'-v', '--verbose',
	help="Be verbose",
	action="store_const", dest="loglevel", const=logging.INFO,
)

# parser.add_argument('--output', 
# 	help="Output base path")
parser.add_argument('--name',
	help="Name for data in storage",
	default="network")
parser.add_argument('--store',
	nargs='?', 
	default="store.h5",
	help="Path for local hdf storage")
parser.add_argument(
		'-r', '--refresh',
		help="Refresh data read cache",
		action="store_true",
		default=False,
	)

args = parser.parse_args()
logging.basicConfig(level=args.loglevel)
store = pd.HDFStore(args.store)



# Load RAW Data
raw_data = parse_raw(args.input)

for i in raw_data:
	if 'df' in raw_data[i]:
		logger.debug('{}'.format(i))
		logger.debug('\n{}\n'.format(raw_data[i]['df'].head()))

# Format
formatted=format_all(raw_data)

df_zone=formatted['zone']
df_tf=formatted['transformer']
df_gen=formatted['gen']
df_branch=formatted['branch']
df_load=formatted['load']
df_bus=formatted['bus']

df_branch['edge']=list(zip(df_branch.bus0,df_branch.bus1))
df_tf['edge']=list(zip(df_tf.bus0,df_tf.bus1))

df_edge=pd.concat([df_branch,df_tf],sort=False)
df_edge['edge_name']=df_edge.index

nodes=list(zip(df_bus.bus,df_bus.to_dict(orient='records')))
edges=list(zip(df_edge.bus0,df_edge.bus1,df_edge.to_dict(orient='records')))

G = nx.Graph()
G.add_nodes_from(nodes)
G.add_edges_from(edges)

def get_edges(row):
	edges=G.edges(row.bus)
	info=[G.edges[edge] for edge in edges]
	names=[i['edge_name'] for i in info]
	return names

# Analyze bus
def analyze_bus(df_bus):
	def get_by_bus(df,fn):
		def get(row):
			return fn(df[df.bus==row.bus])
		return get

	df_bus['gens']=df_bus.apply(get_by_bus(df_gen,lambda x: list(x.index)),axis=1)
	df_bus['p_gen']=df_bus.apply(get_by_bus(df_gen,lambda x: sum(x.p_gen)),axis=1)

	df_bus['loads']=df_bus.apply(get_by_bus(df_load,lambda x: list(x.index)),axis=1)
	df_bus['p_load']=df_bus.apply(get_by_bus(df_load,lambda x: sum(x.p_set)),axis=1)

	df_bus['edges']=df_bus.apply(get_edges,axis=1)

	return df_bus

store_name='{name}bus'.format(name=args.name)
try:
	if args.refresh:	raise Exception
	df_bus = store.get(store_name)
except Exception as e:
	print("Not in storage: {}".format(store_name))
	df_bus = analyze_bus(formatted['bus'])
	store.put(store_name,df_bus)




# print(df_load.head())
# print(df_gen.head())
# print(df_bus.head())
# print(df_tf.head())
# print(df_branch.head())



print('\n\n{}\n'.format(args.name))
print('Load: {}'.format(df_bus.sum().p_load))
print('Gen: {}'.format(df_bus.sum().p_gen))
print('\n\nComponents\n')
for i in formatted:
	print("{}: {}".format(i,len(formatted[i])))

print('\n\nSubgraphs\n')
subgraphs=(G.subgraph(c) for c in nx.connected_components(G))
count=0
for sg in subgraphs:
	count+=1
	if len(sg.nodes)>4:
		print("SG_{}: nodes={} edges={}".format(count,len(sg.nodes),len(sg.edges)))
print('Subgraphs {}'.format(count))
