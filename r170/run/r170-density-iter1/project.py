import flow
from flow import FlowProject, directives
import templates.ndcrc
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)


class Project(FlowProject):
    pass


@Project.post.isfile("ff.xml")
@Project.operation
def create_forcefield(job):
    """Create the forcefield .xml file for the job"""

    content = _generate_r170_xml(job)

    with open(job.fn("ff.xml"), "w") as ff:
        ff.write(content)


@Project.pre.after(create_forcefield)
@Project.post.isfile("system.gro")
@Project.post.isfile("unedited.top")
@Project.operation
def create_system(job):
    """Construct the system in mbuild and apply the forcefield"""

    import mbuild
    import foyer
    import shutil

    r170 = mbuild.load("CC", smiles=True)
    system = mbuild.fill_box(r170, n_compounds=150, density=300)

    ff = foyer.Forcefield(job.fn("ff.xml"))

    system_ff = ff.apply(system)
    system_ff.combining_rule = "lorentz"

    system_ff.save(job.fn("unedited.top"))

    # Get pre-minimized gro file
    shutil.copy("data/initial_config/system_em.gro", job.fn("system.gro"))


@Project.pre.after(create_system)
@Project.post.isfile("system.top")
@Project.operation
def fix_topology(job):
    """Fix the LJ14 section of the topology file

    Parmed is writing the lj14 scaling factor as 1.0.
    GAFF uses 0.5. This function edits the topology
    file accordingly.
    """

    top_contents = []
    with open(job.fn("unedited.top")) as fin:
        for (line_number, line) in enumerate(fin):
            top_contents.append(line)
            if line.strip() == "[ defaults ]":
                defaults_line = line_number

    top_contents[
        defaults_line + 2
    ] = "1               2               yes              0.5       0.8333333\n" #changed no to yes

    with open(job.fn("system.top"), "w") as fout:
        for line in top_contents:
            fout.write(line)


@Project.post.isfile("em.mdp")
@Project.post.isfile("eq.mdp")
@Project.post.isfile("prod.mdp")
@Project.operation
def generate_inputs(job):
    """Generate mdp files for energy minimization, equilibration, production"""

    content = _generate_em_mdp(job)

    with open(job.fn("em.mdp"), "w") as inp:
        inp.write(content)

    content = _generate_eq_mdp(job)

    with open(job.fn("eq.mdp"), "w") as inp:
        inp.write(content)

    content = _generate_prod_mdp(job)

    with open(job.fn("prod.mdp"), "w") as inp:
        inp.write(content)


@Project.label
def em_complete(job):
    if job.isfile("em.gro"):
        return True
    else:
        return False


@Project.label
def eq_complete(job):
    if job.isfile("eq.gro"):
        return True
    else:
        return False


@Project.label
def prod_complete(job):
    if job.isfile("prod.gro"):
        return True
    else:
        return False


@Project.pre.after(create_system)
@Project.pre.after(fix_topology)
@Project.pre.after(generate_inputs)
@Project.post(em_complete)
@Project.post(eq_complete)
@Project.post(prod_complete)
@Project.operation
def simulate(job):
    """Run the minimization, equilibration, and production simulations"""

    command = (
        "gmx_d grompp -f em.mdp -c system.gro -p system.top -o em && "
        "gmx_d mdrun -v -deffnm em -ntmpi 1 -ntomp 1 && "
        "gmx_d grompp -f eq.mdp -c em.gro -p system.top -o eq && "
        "gmx_d mdrun -v -deffnm eq -ntmpi 1 -ntomp 1 && "
        "gmx_d grompp -f prod.mdp -c eq.gro -p system.top -o prod && "
        "gmx_d mdrun -v -deffnm prod -ntmpi 1 -ntomp 1"
    )

    return command


@Project.pre.after(simulate)
@Project.post(lambda job: "density" in job.doc)
@Project.post(lambda job: "density_unc" in job.doc)
@Project.operation
def calculate_density(job):
    """Calculate the density"""

    import panedr
    import numpy as np
    from block_average import block_average

    # Load the thermo data
    df = panedr.edr_to_df(job.fn("prod.edr"))

    # pull density and take average
    density = df[df.Time > 500.0].Density.values
    ave = np.mean(density)

    # save average density
    job.doc.density = ave

    (means_est, vars_est, vars_err) = block_average(density)

    with open(job.fn("density_blk_avg.txt"), "w") as ferr:
        ferr.write("# nblk_ops, mean, vars, vars_err\n")
        for nblk_ops, (mean_est, var_est, var_err) in enumerate(
            zip(means_est, vars_est, vars_err)
        ):
            ferr.write("{}\t{}\t{}\t{}\n".format(nblk_ops, mean_est, var_est, var_err))

    job.doc.density_unc = np.max(np.sqrt(vars_est))


#####################################################################
################# HELPER FUNCTIONS BEYOND THIS POINT ################
#####################################################################
def _generate_r170_xml(job): 

    content = """<ForceField>
 <AtomTypes>
  <Type name="C1" class="c3" element="C" mass="12.010" def="C(C)(H)(H)(H)" desc="carbon"/>
  <Type name="H1" class="hc" element="H" mass="1.008" def="H" desc="H bonded to C"/>
 </AtomTypes>
 <HarmonicBondForce>
  <Bond class1="c3" class2="c3" length="0.1535" k="253634.31000265"/>
  <Bond class1="c3" class2="hc" length="0.1092" k="282252.68637877"/>
 </HarmonicBondForce>
 <HarmonicAngleForce>
  <Angle class1="c3" class2="c3" class3="hc" angle="1.92073484" k="388.01928783"/>
  <Angle class1="hc" class2="c3" class3="hc" angle="1.89106424" k="329.95108893"/>
 </HarmonicAngleForce>
 <PeriodicTorsionForce>
  <Proper class1="hc" class2="c3" class3="c3" class4="hc" periodicity1="3" k1="0.62757555" phase1="0.0"/>
 </PeriodicTorsionForce>
 <NonbondedForce coulomb14scale="0.833333" lj14scale="0.5">
  <Atom type="C1" charge="-0.006120"  sigma="{sigma_C1:0.6f}" epsilon="{epsilon_C1:0.6f}"/>
  <Atom type="H1" charge="0.002040"  sigma="{sigma_H1:0.6f}" epsilon="{epsilon_H1:0.6f}"/>
 </NonbondedForce>
</ForceField>
""".format(
        sigma_C1=job.sp.sigma_C1,
        sigma_H1=job.sp.sigma_H1,
        epsilon_C1=job.sp.epsilon_C1,
        epsilon_H1=job.sp.epsilon_H1,
    )

    return content


def _generate_em_mdp(job):

    contents = """
; MDP file for energy minimization

integrator	    = steep		    ; Algorithm (steep = steepest descent minimization)
emtol		    = 100.0  	    ; Stop minimization when the maximum force < 100.0 kJ/mol/nm
emstep          = 0.01          ; Energy step size
nsteps		    = 50000	  	    ; Maximum number of (minimization) steps to perform

nstlist		    = 1		    ; Frequency to update the neighbor list and long range forces
cutoff-scheme   = Verlet
ns-type		    = grid		; Method to determine neighbor list (simple, grid)
verlet-buffer-tolerance = 1e-5          ; kJ/mol/ps
coulombtype	    = PME		; Treatment of long range electrostatic interactions
rcoulomb	    = 1.0		; Short-range electrostatic cut-off
rvdw		    = 1.0		; Short-range Van der Waals cut-off
pbc		        = xyz 		; Periodic Boundary Conditions (yes/no)
constraints     = all-bonds
lincs-order     = 8
lincs-iter      = 4
"""

    return contents


def _generate_eq_mdp(job):

    contents = """
; MDP file for NVT simulation

; Run parameters
integrator	            = md		    ; leap-frog integrator
nsteps		            = {nsteps}	    ;
dt		                = 0.001		    ; 1 fs

; Output control
nstxout		            = 10000		    ; save coordinates every 10.0 ps
nstvout		            = 0		        ; don't save velocities
nstenergy	            = 100		    ; save energies every 0.1 ps
nstlog		            = 100		    ; update log file every 0.1 ps

; Neighborsearching
cutoff-scheme           = Verlet
ns-type		            = grid		    ; search neighboring grid cells
nstlist		            = 10		    ; 10 fs, largely irrelevant with Verlet
verlet-buffer-tolerance = 1e-5          ; kJ/mol/ps

; VDW
vdwtype                 = Cut-off
rvdw		            = 1.0		    ; short-range van der Waals cutoff (in nm)
vdw-modifier            = None

; Electrostatics
rcoulomb	            = 1.0		    ; short-range electrostatic cutoff (in nm)
coulombtype	            = PME	        ; Particle Mesh Ewald for long-range electrostatics
pme-order	            = 4		        ; cubic interpolation
fourier-spacing         = 0.12          ; effects accuracy of pme
ewald-rtol              = 1e-5

; Temperature coupling is on
tcoupl		            = v-rescale     ; modified Berendsen thermostat
tc-grps		            = System 	    ; Single coupling group
tau-t		            = 0.1	  		; time constant, in ps
ref-t		            = {temp}        ; reference temperature, one for each group, in K

; Pressure coupling is off
pcoupl		            = berendsen
pcoupltype              = isotropic
ref-p                   = {press}
tau-p                   = 0.5
compressibility         = 4.5e-5

; Periodic boundary conditions
pbc		                = xyz		    ; 3-D PBC

; Dispersion correction
DispCorr	            = EnerPres	    ; apply analytical tail corrections

; Velocity generation
gen-vel		            = yes		    ; assign velocities from Maxwell distribution
gen-temp	            = {temp}        ; temperature for Maxwell distribution
gen-seed	            = -1		    ; generate a random seed

constraints             = all-bonds
lincs-order             = 8
lincs-iter              = 4
""".format(
        temp=job.sp.T, press=job.sp.P, nsteps=job.sp.nstepseq
    )

    return contents


def _generate_prod_mdp(job):

    contents = """
; MDP file for NVT simulation

; Run parameters
integrator	            = md		    ; leap-frog integrator
nsteps		            = {nsteps}	    ;
dt		                = 0.001		    ; 1 fs

; Output control
nstxout		            = 10000		    ; save coordinates every 10.0 ps
nstvout		            = 0		        ; don't save velocities
nstenergy	            = 100		    ; save energies every 0.1 ps
nstlog		            = 100		    ; update log file every 0.1 ps

; Neighborsearching
cutoff-scheme           = Verlet
ns-type		            = grid		    ; search neighboring grid cells
nstlist		            = 10		    ; 10 fs, largely irrelevant with Verlet
verlet-buffer-tolerance = 1e-5          ; kJ/mol/ps

; VDW
vdwtype                 = Cut-off
rvdw		            = 1.0		    ; short-range van der Waals cutoff (in nm)
vdw-modifier            = None          ; standard LJ potential

; Electrostatics
rcoulomb	            = 1.0		    ; short-range electrostatic cutoff (in nm)
coulombtype	            = PME	        ; Particle Mesh Ewald for long-range electrostatics
pme-order	            = 4		        ; cubic interpolation
fourier-spacing         = 0.12          ; effects accuracy of pme
ewald-rtol              = 1e-5

; Temperature coupling is on
tcoupl		            = v-rescale     ; Bussi thermostat
tc-grps		            = System 	    ; Single coupling group
tau-t		            = 0.5	  		; time constant, in ps
ref-t		            = {temp}        ; reference temperature, one for each group, in K

; Pressure coupling is off
pcoupl		            = parrinello-rahman
pcoupltype              = isotropic
ref-p                   = {press}
tau-p                   = 1.0
compressibility         = 4.5e-5

; Periodic boundary conditions
pbc		                = xyz		    ; 3-D PBC

; Dispersion correction
DispCorr	            = EnerPres	    ; apply analytical tail corrections

; Velocity generation
gen-vel		            = no		    ; assign velocities from Maxwell distribution
gen-temp	            = {temp}        ; temperature for Maxwell distribution
gen-seed	            = -1		    ; generate a random seed

constraints             = all-bonds
lincs-order             = 8
lincs-iter              = 4
""".format(
        temp=job.sp.T, press=job.sp.P, nsteps=job.sp.nstepsprod
    )

    return contents


if __name__ == "__main__":
    Project().main()
