#!/bin/bash

conda activate hfcs-fffit
module load gcc/9.1.0
source /afs/crc.nd.edu/group/maginn/group_members/Ryan_DeFever/software/gromacs-2020/gromacs-dp/bin/GMXRC

python create_system.py

gmx_d grompp -f em.mdp -c system.gro -p system.top -o system_em
gmx_d mdrun -v -deffnm system_em
