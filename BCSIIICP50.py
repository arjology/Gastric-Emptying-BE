import numpy as np
from scipy.integrate import odeint, simps
from sympy.functions.special.delta_functions import Heaviside
import time, sys
from massBalanceBE import *
from joblib import Parallel, delayed  
import multiprocessing
import csv
import pickle
import bz2
from contextlib import closing

init_time = time.time()

def mySaveFile(title,data):
	# Write the array to disk
	with file(title, 'w') as outfile:
		# I'm writing a header here just for the sake of readability
		# Any line starting with "#" will be ignored by numpy.loadtxt
		outfile.write('# Array shape: {0}\n'.format(np.shape(data)))

		# Iterating through a ndimensional array produces slices along
		# the last axis. This is equivalent to data[i,:,:] in this case
		for data_slice in data:

			# The formatting string indicates that I'm writing out
			# the values in left-justified columns 7 characters in width
			# with 2 decimal places.  
			np.savetxt(outfile, data_slice, fmt='%-7.2f')

			# Writing out a break to indicate different slices...
			outfile.write('# New slice\n')

def myLoadFile(fname,shape):
	# Read the array from disk
	new_data = np.loadtxt(fname)

	# Note that this returned a 2D array!
	print new_data.shapest

# Gastric emptying parameters
p150,p1200 = 0.15, .14
p250, p2200 = .285/(np.pi*15000), .16/(np.pi*3900000)
p350, p3200 = 6.65, 10.4
theta50, theta200 = 1/60.0, 1/60.0
tau50, tau200 = 59.4, 60
s50, s200 = 0.0001, 0.1
KgeParams = np.array([p150,p250,p350,theta50,tau50,s50,p1200,p2200,p3200,theta200,tau200,s200],float)

# Delay parameters
a50,a200 = 2190/50.,2591/100.
b50,b200 = 481/10., 141/10.
c50,c200 = 27/25., 11/20.
d50,d200 = 531/25. ,138/5.
e50,e200 = 13/200. ,6/25.
f50,f200 = 41/100., -59/50. 
LagParams = np.array([a50,b50,c50,d50,e50,f50,a200,b200,c200,d200,e200,f200],float)

randKgeParam = []
randKgeParam.append(KgeParams*np.transpose([np.concatenate(([1.0],np.array((10-np.random.uniform(-1,1,23))/10,float)))]))
randKgeParam = randKgeParam[0]

randLagParam = []
randLagParam.append(LagParams*np.transpose([np.concatenate(([1.0],np.array((10-np.random.uniform(-1,1,23))/10,float)))]))
randLagParam = randLagParam[0]

# Initial doses
dose = 100.0
vol = 50

KpelVals = np.array([0.1, .05, .0231, .011552, .002888],float)

t = np.arange(0,4000,1)
title = 'BCS III Const Peff $50mL$'
perm0,perm1,perm2,perm3,perm4,perm5,perm6 = np.ones(7)*0.005
PermRates = [perm0,perm1,perm2,perm3,perm4,perm5,perm6]
M0 = np.array([dose,0,0,0,0,0,0,0,0],float)

inputs = range(121)
num_cores = multiprocessing.cpu_count()

def solve_to(i):
	to = i
	x = massBalance( t, to, Kpel, PermRates, patientKgeParams, patientLagParams, vol, M0,title)
	Mresult = x.solveSys(t)
	return Mresult
def c_max(data):
	return np.max(data[:,-1])
def t_max(data):
	return t[np.argmax(data[:,-1])]
def area(data):
	return simps(data[:,-1], dx=1)

MresultList50, cMaxList50, tMaxList50, AUCList50 = [],[],[],[]
start_time = time.time()
totIts = len(KpelVals)*len(range(24))
bar_length = 20
for j in range(5):
	Kpel = KpelVals[j]
	for k in range(24):
		#print('[Patient=%d\tKel=%.2f]'%(k, KpelVals[j]))
		patientKgeParams = randKgeParam[k]
		patientLagParams = randLagParam[k]
		result = Parallel(n_jobs=num_cores)(delayed(solve_to)(i) for i in inputs)
		cMax = Parallel(n_jobs=num_cores)(delayed(c_max)(result[i]) for i in inputs)
		tMax = Parallel(n_jobs=num_cores)(delayed(t_max)(result[i]) for i in inputs)
		AUC = Parallel(n_jobs=num_cores)(delayed(area)(result[i]) for i in inputs)				
		MresultList50.append(np.array(result)[:,:,-1])
		cMaxList50.append(np.array(cMax))
		tMaxList50.append(np.array(tMax))
		AUCList50.append(np.array(AUC))
		
		percent = float(((j)*24.+(k+1))/totIts)
		hashes = '#' * int(round(percent * bar_length))
		spaces = ' ' * (bar_length - len(hashes))
		runtime = round(time.time()-start_time,2)
		sys.stdout.write("\rPercent: [{0}] {1}% completed in {2} seconds".format(hashes + spaces, int(round(percent * 100)), runtime))
		sys.stdout.flush()
		
print("--- Parallelized execution completed: %s seconds ---" % float(time.time() - float(start_time)))

print("--- Name: %s  ---" % title)
print("--- Data sizes:   ---")
print("Solutions: %s"  % repr(np.shape(MresultList50)))
print("cMax: %s"%repr(np.shape(cMaxList50)))
print("tMax: %s"%repr(np.shape(tMaxList50)))
print("AUC: %s"%repr(np.shape(AUCList50)))

fname = title.replace(" ","").replace('$','').replace('_','').replace('$','').replace('{','').replace('}','').replace('in','_')	
fnameConc,fnamecMax,fnametMax,fnameAUC = fname+'_conc',fname+'_cMax',fname+'_tMax',fname+'_AUC'

print("--- Saving resutls: %s ---" % fname)
start_time = time.time()
totIts = len(KpelVals)*len(range(24))
bar_length = 20
for j in range(5):
	for k in range(24):
		#print repr(MresultList50[(j)*24+k].shape)
		np.savetxt(fnameConc + '_Elim' + repr(j+1) + '_P_' + repr(k+1) + '.csv', MresultList50[(j)*24+k], delimiter=',')
		np.savetxt(fnamecMax + '_Elim' + repr(j+1) + '_P_' + repr(k+1) + '.csv', cMaxList50[(j)*24+k], delimiter=',')
		np.savetxt(fnametMax + '_Elim' + repr(j+1) + '_P_' + repr(k+1) + '.csv', tMaxList50[(j)*24+k], delimiter=',')
		np.savetxt(fnameAUC + '_Elim' + repr(j+1) + '_P_' + repr(k+1) + '.csv', AUCList50[(j)*24+k], delimiter=',')
		
		percent = float(((j)*24.+(k+1))/totIts)
		hashes = '#' * int(round(percent * bar_length))
		spaces = ' ' * (bar_length - len(hashes))
		runtime = round(time.time()-start_time,2)
		sys.stdout.write("\rPercent: [{0}] {1}% completed in {2} seconds".format(hashes + spaces, int(round(percent * 100)), runtime))
		sys.stdout.flush()
		    
print("--- Completed! Total execution time: %s seconds ---" % float(time.time() - float(init_time)))

