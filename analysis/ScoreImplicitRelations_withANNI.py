import argparse
from math import log
from collections import defaultdict

from multiprocessing import Pool,Manager
from functools import partial
from contextlib import closing
import time
import logging
import sys

def D(v,w,cooccurrences,occurrences):
	p1 = cooccurrences[(v,w)] / float(occurrences[v])
	p2 = cooccurrences[(v,w)] / float(occurrences[w])
	return max(p1,p2)

def calculateFactaPlusScore(x,z,neighbours,cooccurrences,occurrences):
	shared = neighbours[x].intersection(neighbours[z])
	product = 1.0
	for y in shared:
		tmp = 1.0 - D(x,y,cooccurrences,occurrences) * D(y,z,cooccurrences,occurrences)
		product *= tmp
	return 1.0 - product

def calculateBitolaScore(x,z,neighbours,cooccurrences,occurrences):
	shared = neighbours[x].intersection(neighbours[z])
	total = 0
	for y in shared:
		total += cooccurrences[(x,y)] * cooccurrences[(y,z)]
	return total

def calculateArrowsmithScore(x,z,neighbours,cooccurrences,occurrences):
	shared = neighbours[x].intersection(neighbours[z])
	return len(shared)

def calculateJaccardIndex(x,z,neighbours,cooccurrences,occurrences):
	shared = neighbours[x].intersection(neighbours[z])
	combined = neighbours[x].union(neighbours[z])
	return len(shared)/float(len(combined))

def calculatePreferentialAttachment(x,z,neighbours,cooccurrences,occurrences):
	score = len(neighbours[x]) + len(neighbours[z])
	return score

def H1(i,occurrences,sentenceCount):
	N_i = float(occurrences[i])
	N = float(sentenceCount)
	score = -(N_i/N) * log(N_i/N) - ((N-N_i)/N) * log((N-N_i)/N)
	return score

def H2(i,j,cooccurrences,occurrences,sentenceCount):
	N_ij = 0
	if (i,j) in cooccurrences:
		N_ij = float(cooccurrences[(i,j)])
	N_i = float(occurrences[i])
	N_j = float(occurrences[j])
	N = float(sentenceCount)

	old = False

	if old:
		if N_ij==0 or (N_j-N_ij)==0 or (N_i-N_ij)==0 or (N-N_j-N_i)==0:
			return 0.0
		else:
			score = -(N_ij/N) * log(N_ij/N)
			score += - ((N_j-N_ij)/N) * log((N_j-N_ij)/N)
			score += - ((N_i-N_ij)/N) * log((N_i-N_ij)/N)
			score += - ((N-N_j-N_i)/N) * log((N-N_j-N_i)/N)
			return score
	
	else:
		score = 0.0

		if N_ij != 0:
			score += -(N_ij/N) * log(N_ij/N) 
		if (N_j-N_ij) != 0:
			score += - ((N_j-N_ij)/N) * log((N_j-N_ij)/N)
		if (N_i-N_ij) != 0:
			score += - ((N_i-N_ij)/N) * log((N_i-N_ij)/N)
		if (N-N_j-N_i) != 0:
			score += - ((N-N_j-N_i)/N) * log((N-N_j-N_i)/N)

		return score

def U(i,j,cooccurrences,occurrences,sentenceCount):
	
	H_i = H1(i,occurrences,sentenceCount)
	H_j = H1(j,occurrences,sentenceCount)

	H_i_j = H2(i,j,cooccurrences,occurrences,sentenceCount)

	numerator = H_i + H_j - H_i_j
	denominator = 0.5 * (H_i + H_j)

	if (i<10 and j<10):
		print "DEBUG\t%d\t%d\t%f\t%f\t%f\t%f\t%f\t%f" % (i,j,H_i,H_j,H_i_j,numerator,denominator,numerator/denominator)
	
	if denominator == 0:
		return 0.0
	else:
		return numerator/denominator

def calcANNIVector(allEntities,cooccurrences,occurrences,sentenceCount,queue,x):
	try:
		anniVector = [ U(x,y,cooccurrences,occurrences,sentenceCount) for y in allEntities ]
	#except Exception:
	#	logging.exception("f(%r) failed" % (x,))
	except:
		print "Unexpected error:", sys.exc_info()[0], x
		raise
		
	#print x
	queue.put(x)
	return anniVector

def prepareANNIConceptVectors(entitiesToScore,neighbours,cooccurrences,occurrences,sentenceCount):
	allEntities = sorted(list(occurrences.keys()))
	#conceptVectors = { x: [ U(x,y,cooccurrences,occurrences,sentenceCount) for y in allEntities ] for x in entitiesToScore }
	
	conceptVectors = {}
	for x in entitiesToScore:
		conceptVectors[x] = [ U(x,y,cooccurrences,occurrences,sentenceCount) for y in allEntities ]

	return conceptVectors
				
def calculateANNIScore(x,z,conceptVectors):
	vectorX = conceptVectors[x]
	vectorZ = conceptVectors[z]
	#entities = vectorX.keys().intersection(vectorZ.keys())
	#dotprod = sum( [ vectorX[e]*vectorZ[e] for e in entities ] )
	assert len(vectorX) == len(vectorZ)
	dotprod = sum( [ i*j for i,j in zip(vectorX,vectorZ) ] )
	return dotprod

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Calculate scores for a set of scores')
	parser.add_argument('--cooccurrenceFile',type=str,required=True,help='File containing cooccurrences')
	parser.add_argument('--occurrenceFile',type=str,required=True,help='File containing occurrences')
	parser.add_argument('--sentenceCount',type=str,required=True,help='File containing sentence count')
	parser.add_argument('--relationsToScore',type=str,required=True,help='File containing relations to score')
	parser.add_argument('--outFile',type=str,required=True,help='File to output scores to')
	parser.add_argument('--outANNIVectors',type=str,help='File to output ANNI vectors to')

	args = parser.parse_args()

	print "Loading relationsToScore"
	relationsToScore = set()
	entitiesToScore = set()
	with open(args.relationsToScore) as f:
		for line in f:
			x,y,_ = map(int,line.strip().split())
			relationsToScore.add((x,y))
			entitiesToScore.add(x)
			entitiesToScore.add(y)
	relationsToScore = sorted(list(relationsToScore))
	entitiesToScore = sorted(list(entitiesToScore))
	print "Loaded relationsToScore"

	print "Loading sentenceCount"
	sentenceCount = None
	with open(args.sentenceCount) as f:
		sentenceCount = int(f.readline().strip())
	print "Loaded sentenceCount"

	print "Loading occurrences..."
	occurrences = {}
	with open(args.occurrenceFile) as f:
		for line in f:
			x,count = map(int,line.strip().split())
			occurrences[x] = count
	print "Loaded occurrences"

	print "Loading cooccurrences..."
	cooccurrences = {}
	neighbours = defaultdict(set)
	with open(args.cooccurrenceFile) as f:
		for line in f:
			x,y,count = map(int,line.strip().split())
			cooccurrences[(x,y)] = count
			cooccurrences[(y,x)] = count
			neighbours[x].add(y)
			neighbours[y].add(x)
	print "Loaded cooccurrences"

	print "Preparing ANNI concept vectors..."
	anniConceptVectors = prepareANNIConceptVectors(entitiesToScore,neighbours,cooccurrences,occurrences,sentenceCount)
	print "Prepared ANNI concept vectors"

	if args.outANNIVectors:
		print "Saving ANNI vectors..."
		conceptIDs = sorted(anniConceptVectors.keys())
		with open(args.outANNIVectors,'w') as outF:
			for conceptID in conceptIDs:
				outData = [conceptID] + anniConceptVectors[conceptID]
				outLine = "\t".join(map(str,outData))
				outF.write(outLine+"\n")
		print "Saved ANNI vectors"

	print "Scoring..."
	with open(args.outFile,'w') as outF:
		for i,(x,z) in enumerate(relationsToScore):
			if (i%10000) == 0:
				print i
			factaPlusScore = calculateFactaPlusScore(x,z,neighbours,cooccurrences,occurrences)
			bitolaScore = calculateBitolaScore(x,z,neighbours,cooccurrences,occurrences)
			anniScore = calculateANNIScore(x,z,anniConceptVectors)
			arrowsmithScore = calculateArrowsmithScore(x,z,neighbours,cooccurrences,occurrences)
			jaccardScore = calculateJaccardIndex(x,z,neighbours,cooccurrences,occurrences)
			preferentialAttachmentScore = calculatePreferentialAttachment(x,z,neighbours,cooccurrences,occurrences)

			#outData = [x,z,factaPlusScore,bitolaScore,anniScore,arrowsmithScore,jaccardScore,preferentialAttachmentScore]
			outData = [x,z,anniScore]
			outLine = "\t".join(map(str,outData))
			outF.write(outLine+"\n")

	print "Completed scoring"
	print "Output to %s" % args.outFile

