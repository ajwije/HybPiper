#!/usr/bin/env python

import argparse, os, sys, shutil, subprocess

helptext='''Run the assembler SPAdes with re-dos if any of the k-mers are unsuccessful.
The re-runs are attempted by removing the largest k-mer and re-running spades. If a final
contigs.fasta file is generated, a 'spades.ok' file is saved.'''


def make_spades_cmd(genelist,cov_cutoff=8,cpu=None,paired=True,kvals=None,redo=False):
	
	if paired:
		fileflag = "--12"
	else:
		fileflag = "-s"
	
	if kvals:
		kvals = ",".join(kvals)

	if cpu:
		if kvals:
			spades_cmd = "time parallel -j {} --eta spades.py --only-assembler -k {} --threads 1 --cov-cutoff {} {} {{}}/{{}}_interleaved.fasta -o {{}}/{{}}_spades :::: {} > spades.log".format(cpu,kvals,cov_cutoff,fileflag,genelist)
		else:
			spades_cmd = "time parallel -j {} --eta spades.py --only-assembler --threads 1 --cov-cutoff {} {} {{}}/{{}}_interleaved.fasta -o {{}}/{{}}_spades :::: {} > spades.log".format(cpu,cov_cutoff,fileflag,genelist)
	else:
		if kvals:
			spades_cmd = "time parallel --eta spades.py --only-assembler -k {} --threads 1 --cov-cutoff {} {} {{}}/{{}}_interleaved.fasta -o {{}}/{{}}_spades :::: {} > spades.log".format(kvals,cov_cutoff,fileflag,genelist)
		else:
			spades_cmd = "time parallel --eta spades.py --only-assembler --threads 1 --cov-cutoff {} {} {{}}/{{}}_interleaved.fasta -o {{}}/{{}}_spades :::: {} > spades.log".format(cov_cutoff,fileflag,genelist)
	return spades_cmd

def spades_initial(genelist,cov_cutoff=8,cpu=None,paired=True,kvals=None):
	"Run SPAdes on each gene separately using GNU paralell."""
	if os.path.isfile("spades.log"):
		os.remove("spades.log")
	
	genes = [x.rstrip() for x in open(genelist)]
	spades_cmd = make_spades_cmd(genelist,cov_cutoff,cpu,paired,kvals)
	
	sys.stderr.write("Running SPAdes on {} genes\n".format(len(genes)))
	sys.stderr.write(spades_cmd + "\n")
	exitcode = subprocess.call(spades_cmd,shell=True)

	if exitcode:
		sys.stderr.write("ERROR: One or more genes had an error with SPAdes assembly. This may be due to low coverage. No contigs found for the following genes:\n")
	
	spades_successful = []
	spades_failed = []
	
	for gene in genes:
		if os.path.isfile("{}/{}_spades/contigs.fasta".format(gene,gene)):
			shutil.copy("{}/{}_spades/contigs.fasta".format(gene,gene),"{}/{}_contigs.fasta".format(gene,gene))
			spades_successful.append(gene)
		else:
			sys.stderr.write("{}\n".format(gene))
			spades_failed.append(gene)
	return spades_failed

def rerun_spades(genelist,cov_cutoff=8,cpu=None, paired = True):
	genes = [x.rstrip() for x in open(genelist)]
	
	redo_cmds_file = open("redo_spades_commands.txt",'w')
	
	spades_successful = []
	spades_failed = []
	spades_duds = []
	
	genes_redos = []
	
	all_redo_kmers = []
	restart_ks = []
	for gene in genes:
		all_kmers = [int(x[1:]) for x in os.listdir(os.path.join(gene,"{}_spades".format(gene))) if x.startswith("K")]
		all_kmers.sort()
		
		if len(all_kmers) < 2:
			sys.stderr.write("WARNING: All Kmers failed for {}!\n".format(gene))
			spades_duds.append(gene)
			continue
		else:
			genes_redos.append(gene)	
		redo_kmers = [str(x) for x in all_kmers[:-1]]
		restart_k = "k{}".format(redo_kmers[-1])
		kvals = ",".join(redo_kmers)
		spades_cmd = "spades.py --restart-from {} -k {} --threads 1 --cov-cutoff {} -o {}/{}_spades".format(restart_k,kvals,cov_cutoff,gene,gene)
		redo_cmds_file.write(spades_cmd + "\n")
	
	redo_cmds_file.close()
	if cpu:
		redo_spades_cmd = "parallel -j {} --eta :::: redo_spades_commands.txt > spades_redo.log".format(cpu) 	
	else:
		redo_spades_cmd = "parallel --eta :::: redo_spades_commands.txt > spades_redo.log" 	
		
	
	with open("spades_duds.txt",'w') as spades_duds_file:
		spades_duds_file.write("\n".join(spades_duds))
	
	sys.stderr.write("Re-running SPAdes for {} genes\n".format(len(genes_redos)))
	sys.stderr.write(redo_spades_cmd+"\n")
	exitcode = subprocess.call(redo_spades_cmd,shell=True)
	

	
	if exitcode:
		sys.stderr.write("ERROR: One or more genes had an error with SPAdes assembly. This may be due to low coverage. No contigs found for the following genes:\n")
		
	for gene in genes_redos:
		gene_failed = False
		if os.path.isfile("{}/{}_spades/contigs.fasta".format(gene,gene)):
			if os.stat("{}/{}_spades/contigs.fasta").st_size > 0:
				shutil.copy("{}/{}_spades/contigs.fasta".format(gene,gene),"{}/{}_contigs.fasta".format(gene,gene))
				spades_successful.append(gene)
			else:
				gene_failed = True
		else:
			gene_failed = True
			
		if gene_failed:
			sys.stderr.write("{}\n".format(gene))
			spades_failed.append(gene)
	return spades_failed,spades_duds
	



def main():
	parser = argparse.ArgumentParser(description=helptext,formatter_class=argparse.RawTextHelpFormatter)
	parser.add_argument('genelist',help="Text file containing the name of each gene to conduct SPAdes assembly. One gene per line, should correspond to directories within the current directory.")
	parser.add_argument('--cpu',type=int,default=0,help="Limit the number of CPUs. Default is to use all cores available.")
	parser.add_argument('--cov_cutoff',type=int,default=8,help="Coverage cutoff for SPAdes. default: %(default)s")
	parser.add_argument("--kvals",nargs='+',help="Values of k for SPAdes assemblies. Default is to use SPAdes auto detection based on read lengths (recommended).",default=None)
	parser.add_argument("--redos_only",action="store_true",default=False,help="Continue from previously assembled SPAdes assemblies and only conduct redos from failed_spades.txt")
	
	args = parser.parse_args()
	
	if os.path.isfile("failed_spades.txt") and args.redos_only:
		spades_failed = rerun_spades("failed_spades.txt")
	else:	
		spades_failed = spades_initial(args.genelist,cov_cutoff=args.cov_cutoff,cpu=args.cpu,kvals=args.kvals)	
	
		if len(spades_failed) > 0:
			with open("failed_spades.txt",'w') as failed_spadefile:
				failed_spadefile.write("\n".join(spades_failed))
		
			spades_failed,spades_duds = rerun_spades("failed_spades.txt",cov_cutoff=args.cov_cutoff)
			if len(spades_failed) == 0:
				sys.stderr.write("All redos completed successfully!\n")
			else:
				sys.exit(1)
	
if __name__ == "__main__":main()
