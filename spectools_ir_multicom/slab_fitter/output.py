import numpy as np
import emcee
import pandas as pd
from IPython.display import display, Math
import corner
import matplotlib.pyplot as plt

from astropy.io import fits
from astropy.constants import c,h, k_B, G, M_sun, au, pc, u
from astropy.table import Table
from astropy import units as un

from spectools_ir_multicom.utils import extract_hitran_data, get_global_identifier, translate_molecule_identifier, get_molmass

def compute_fluxes_single(mydata,theta):
    logn,logtemp,logomega=theta  #logt
    temp=10**logtemp #logt
    omega=10**logomega
    n_col=10**logn
    si2jy=1e26   #SI to Jy flux conversion factor 
#If local velocity field is not given, assume sigma given by thermal velocity
    mu=u.value*mydata.molmass
    deltav=np.sqrt(k_B.value*temp/mu)   #m/s
#Use line_ids to extract relevant HITRAN data
    wn0=mydata.wn0
    aup=mydata.aup
    eup=mydata.eup
    gup=mydata.gup
    eup_k=mydata.eup_k
    elower=mydata.elower

#Compute partition function                    
    q=_get_partition_function(mydata,temp)
#Begin calculations
    afactor=((aup*gup*n_col)/(q*8.*np.pi*(wn0)**3.)) #mks
    efactor=h.value*c.value*eup/(k_B.value*temp)
    wnfactor=h.value*c.value*wn0/(k_B.value*temp)
    phia=1./(deltav*np.sqrt(2.0*np.pi))
    efactor2=eup_k/temp
    efactor1=elower*1.e2*h.value*c.value/k_B.value/temp
    tau0=afactor*(np.exp(-1.*efactor1)-np.exp(-1.*efactor2))*phia  #Avoids numerical issues at low T 
    w0=1.e6/wn0

    dvel=0.1e0    #km/s                                     
    nvel=1001
    vel=(dvel*(np.arange(0,nvel)-500.0))*1.e3     #now in m/s
#Now loop over transitions and velocities to calculate flux 
    tau=np.exp(-vel**2./(2.*np.vstack(deltav)**2.))*np.vstack(tau0)

#Create array to hold line fluxes (one flux value per line) 
    nlines=np.size(tau0)
    f_arr=np.zeros([nlines,nvel])     #nlines x nvel
    lineflux=np.zeros(nlines)

    for i in range(nlines):  #I might still be able to get rid of this loop 
        f_arr[i,:]=2*h.value*c.value*wn0[i]**3./(np.exp(wnfactor[i])-1.0e0)*(1-np.exp(-tau[i,:]))*si2jy*omega
        lineflux_jykms=np.sum(f_arr[i,:])*dvel
        lineflux[i]=lineflux_jykms*1e-26*1.*1e5*(1./(w0[i]*1e-4))    #mks  
    return lineflux    


def compute_model_fluxes(mydata,samples,bestfit=None):
    '''
    Function to compute model fluxes for same lines as in dataset.

    Parameters
    ----------
    mydata : Data object
     Instance of Data class, provides routine with lines to calculate
    samples : numpy array
     Array holding arrays of MCMC output samples.  Used to find best-fit parameters.s

    Returns
    ---------
    lineflux : numpy array
     Array of line fluxes 
    '''

    Ncom=get_ncom(samples)  #Number of components

#    bestfit_dict=find_best_fit(samples)

    if(bestfit is None):  #best fit not specified, use 50th percentile from fit
        theta=[]
        for i in range(3*Ncom):
            theta.append(np.percentile(samples[:, i], [16, 50, 84])[1])
    else:
        theta=bestfit
            
    for i in range(Ncom):
        mytheta=theta[3*i:3*i+3]
        mylineflux=compute_fluxes_single(mydata,mytheta)
        if (i==0): lineflux=mylineflux
        else: lineflux+=mylineflux

    return lineflux


def get_samples(chain,burnin):
    '''                                                                                                                          
    Function to remove burnin samples from MCMC output chain, reconfigure to make samples
                                                                                                                                 
    Parameters                                                                                                                   
    ----------                                                                                                                   
    presamples : numpy array                                                                                                     
     Array holding arrays of MCMC output samples.  Used to find best-fit parameters.s                                            
    burnin : integer                                                                                                             
     Number of samples considered part of the "burnin"                                                                           
                                                                                                                                 
    Returns                                                                                                                      
    ---------                                                                                                                    
    postsamples : numpy array                                                                                                    
     Array holding arrays of MCMC output samples after removal of burnin samples.                                                
    '''
    ndims = chain.shape[2]
    samples = chain[:, burnin:, :].reshape((-1, ndims))
    
    return samples

def get_lnprob(mysampler,burnin):
    lnprob=mysampler.lnprobability[:,burnin:].reshape(-1)
    
    return lnprob

def _get_partition_function(mydata,temp):
    q=np.zeros(mydata.nlines)
    for myunique_id in mydata.unique_globals:
        myq=mydata.qdata_dict[str(myunique_id)][int(temp)-1]
        mybool=(mydata.global_id == myunique_id)
        q[mybool]=myq
    return q

def corner_plot(samples,outfile=None,**kwargs):
    '''
    Function to make a corner plot for output samples

    Parameters
    ----------
    samples : numpy array
     Array holding arrays of MCMC output samples.
    outfile : str, optional
     Path to output file to hold resultant figure
    '''
    Ncom=get_ncom(samples)  #Number of components
    parlabels=[]
    paramkeys=[]
    perrkeys=[]
    nerrkeys=[]
    for i in range(Ncom):
        parlabels.append(r"$\log(\ n_\mathrm{tot} [\mathrm{m}^{-2}]\ )$"+'_'+str(i))
#        parlabels.append(r"Temperature [K]"+'_'+str(i))
        parlabels.append(r"$\log(\ \mathrm{Temperature [K]})$"+'_'+str(i)) #logt
        parlabels.append(r"$\log(\ {\Omega [\mathrm{rad}]}\ )$"+'_'+str(i))
#    parlabels=[ r"$\log(\ n_\mathrm{tot} [\mathrm{m}^{-2}]\ )$",r"Temperature [K]", "$\log(\ {\Omega [\mathrm{rad}]}\ )$"]
    fig = corner.corner(samples,
                    labels=parlabels,
                    show_titles=True, title_kwargs={"fontsize": 12},quantiles=[0.16, 0.5, 0.84],**kwargs)
    if(outfile is not None):
        fig.savefig(outfile)

def trace_plot(samples,xr=[None,None]):
    '''
    Function to make a trace plot for each parameter of slab model fit

    Parameters
    ----------
    samples : numpy array
     Array holding arrays of MCMC output samples. 
    xr : 2-element array, optional
     Range of samples to plot
    '''

    Ncom=get_ncom(samples)  #Number of components

    fig, axes = plt.subplots(Ncom*3, figsize=(10, Ncom*6), sharex=True)
#    parlabels=Ncom*[ r"$\log(\ n_\mathrm{tot} [\mathrm{m}^{-2}]\ )$",r"Temperature [K]", "$\log(\ {\Omega [\mathrm{rad}]}\ )$"]

    parlabels=[]
    paramkeys=[]
    perrkeys=[]
    nerrkeys=[]
    for i in range(Ncom):
        parlabels.append(r"$\log(\ n_\mathrm{tot} [\mathrm{m}^{-2}]\ )$"+'_'+str(i))
#        parlabels.append(r"Temperature [K]"+'_'+str(i))
        parlabels.append(r"$\log(\ $Temperature [K]$)$"+'_'+str(i)) #logt
        parlabels.append(r"$\log(\ {\Omega [\mathrm{rad}]}\ )$"+'_'+str(i))

    ndims=3*Ncom
    for i in range(ndims):
        ax = axes[i]
        ax.plot(samples[:,i], "k", alpha=0.3)    #0th walker, i'th dimension
        ax.set_ylabel(parlabels[i])
        ax.yaxis.set_label_coords(-0.1, 0.5)
        ax.set_xlim(xr)
    axes[-1].set_xlabel("step number");

def get_ncom(samples):
    Ncom=int(np.size(samples[0])/3)
    return Ncom

def find_best_fit(samples,show=False):
    '''
    Function to find best fit parameters

    Parameters
    ----------
    samples : numpy array
     Array holding arrays of MCMC output samples.
    show : boolean, optional
     Boolean to display or not display nicely-formatted results

    Returns
    ---------
    bestfit_dict : 
     Dictionary holding best-fit slab model parameters with plus and minus error bars.
     Based on 16, 50 and 84th percentiles of posterior distribution.
    '''
    Ncom=get_ncom(samples)  #Number of components

    parlabels=[]
    paramkeys=[]
    perrkeys=[]
    nerrkeys=[]
    for i in range(Ncom):
        parlabels.append(r"\log(\ n_\mathrm{tot} [\mathrm{m}^{-2}]\ )"+'_'+str(i))
        parlabels.append(r"\log(Temperature [K])"+'_'+str(i)) #logt
#        parlabels.append(r"Temperature [K]"+'_'+str(i))
        parlabels.append(r"\log(\ {\Omega [\mathrm{rad}]}\ )"+'_'+str(i))
        paramkeys.append('logN'+'_'+str(i))
        paramkeys.append('logT'+'_'+str(i)) #logt
#        paramkeys.append('T'+'_'+str(i))
        paramkeys.append('logOmega'+'_'+str(i))
        perrkeys.append('logN_perr'+'_'+str(i))
        perrkeys.append('logT_perr'+'_'+str(i)) #logt
#        perrkeys.append('T_perr'+'_'+str(i))
        perrkeys.append('logOmega_perr'+'_'+str(i))
        nerrkeys.append('logN_nerr'+'_'+str(i))
#        nerrkeys.append('T_nerr'+'_'+str(i))
        nerrkeys.append('logT_nerr'+'_'+str(i)) #logt
        nerrkeys.append('logOmega_nerr'+'_'+str(i))

    theta=[]
    bestfit_dict={}
    for i in range(3*Ncom):
        mcmc = np.percentile(samples[:, i], [16, 50, 84])
        q = np.diff(mcmc)
        txt = "\mathrm{{{3}}} = {0:.3f}_{{-{1:.3f}}}^{{{2:.3f}}}"
        txt = txt.format(mcmc[1], q[0], q[1], parlabels[i])
        if(show==True): display(Math(txt))
        bestfit_dict[paramkeys[i]]=mcmc[1]
        bestfit_dict[perrkeys[i]]=q[1]     
        bestfit_dict[nerrkeys[i]]=q[0]    
        theta.append(mcmc[1])

    bestfit_dict['theta']=theta

    return bestfit_dict
