import numpy as np
import urllib
import emcee
import pandas as pd
import json as json
import time
import pkgutil

import pdb as pdb
from astropy.io import fits
from astropy.constants import c,h, k_B, G, M_sun, au, pc, u
from astropy.table import Table
from astropy import units as un

from spectools_ir_multicom.utils import extract_hitran_data, get_global_identifier, translate_molecule_identifier, get_molecule_identifier, get_molmass
import pdb as pdb

def read_data_from_file(filename,vup=None,**kwargs):
    '''
    Convenience function to find all HITRAN data for lines, given minimal inputs (local_iso_id, molec_id, lineflux, lineflux_err, wn or wave)
    
    Parameters
    ----------
    filename : str
     Name of file containing line fluxes, isotope ids, molecular ids, and line flux errors    

    Returns
    ----------
    data : pandas data frame
     More complete pandas data frame containing HITRAN data in addition to input line fluxes    
    '''

    data=pd.read_csv(filename,sep=r"\s+")
    data['local_iso_id'] = data.pop('iso')
    data['molec_id']=data['molec'].apply(get_molecule_identifier)
    data['lineflux_err']=data.pop('error')

    if(('wave' in data.columns) and ('wn' not in data.columns)): data['wn']=1.e4/data.wave

    if not ('a' in data and 'gup' in data and 'elower' in data):
        wavemin=1e4/(np.max(data['wn'])+2)
        wavemax=1e4/(np.min(data['wn'])-2)
        if(not ('a' in data)):  
            nota=True
            data['a']=np.zeros(np.shape(data)[0])
        else: nota=False

        if(not ('gup' in data)):  
            notgup=True
            data['gup']=np.zeros(np.shape(data)[0])
        else: notgup=False

        if(not ('elower' in data)):  
            notelower=True            
            data['elower']=np.zeros(np.shape(data)[0])
        else: notelower=False

        mol_iso_id=data['molec_id'].astype(str)+'_'+data['local_iso_id'].astype(str)
        unique_ids,unique_indices=np.unique(mol_iso_id,return_index=True)
        for i,myunique_id in enumerate(unique_ids):
            hitran_data=extract_hitran_data(data['molec'][unique_indices[i]], wavemin, wavemax, isotopologue_number=data['local_iso_id'][unique_indices[i]],vup=vup,**kwargs)
            loc=np.where(mol_iso_id==myunique_id)[0]

            for myloc in loc:
                pos=np.argmin(np.abs(hitran_data['wn']-data['wn'][myloc]))
                if(nota):  data.at[myloc,'a']=hitran_data['a'][pos]
                if(notgup):  data.at[myloc,'gup']=hitran_data['gp'][pos]
                if(notelower):  data.at[myloc,'elower']=hitran_data['elower'][pos]

    data['eup_k']=(data['elower']+data['wn'])*1e2*h*c/k_B

    data.drop('molec',axis=1)
    return data

class Config():
    '''
    Class for handling input parameters
    '''
    def __init__(self,config_file=None):
        if(config_file is None):
            config_data=pkgutil.get_data(__name__,'config.json')
            self.config=json.loads(config_data)
        if(config_file is not None):
            with open(config_file, 'r') as file:
                self.config = json.load(file)

    def getpar(self,name):
        return self.config[name]

    def display(self):
 
        print(json.dumps(self.config, indent=1))

class Retrieval():
    '''
    Class for handling the Bayesian retrieval using the emcee package.
    
    '''
    def __init__(self,Config,LineData):
        self.Config = Config
        self.LineData = LineData

    def run_emcee(self):
        Nwalkers=self.Config.getpar('Nwalkers')
        Nsamples=self.Config.getpar('Nsamples')
        Nburnin=self.Config.getpar('Nburnin')
        Ncom=self.Config.getpar('Ncom')

        #Initialize walkers
        samplearr=[]

        if(Ncom==1):
            lognini = np.random.uniform(self.Config.getpar('lognmin'), self.Config.getpar('lognmax'), Nwalkers) # initial logn points 
            samplearr.append(lognini)
            logtini = np.random.uniform(self.Config.getpar('logtmin'), self.Config.getpar('logtmax'), Nwalkers) # initial logt points  #logt
            samplearr.append(logtini) #logt
            logomegaini = np.random.uniform(self.Config.getpar('logomegamin'), self.Config.getpar('logomegamax'), Nwalkers) # initial logomega points 
            samplearr.append(logomegaini)

        if(Ncom>1):
            for i in np.arange(Ncom):
                lognini = np.random.uniform(self.Config.getpar('lognmin_'+str(i)), self.Config.getpar('lognmax_'+str(i)), Nwalkers) # initial logn points
                samplearr.append(lognini)
                logtini = np.random.uniform(self.Config.getpar('logtmin_'+str(i)), self.Config.getpar('logtmax_'+str(i)), Nwalkers) # initial logt points #logt
                samplearr.append(logtini)   #logt
                logomegaini = np.random.uniform(self.Config.getpar('logomegamin_'+str(i)), self.Config.getpar('logomegamax_'+str(i)), Nwalkers) # initial logn points 
                samplearr.append(logomegaini)

        inisamples=np.array(samplearr).T
        ndims = inisamples.shape[1]
        sampler = emcee.EnsembleSampler(Nwalkers, ndims, self._lnposterior)

        start_time=time.time()
        sampler.run_mcmc(inisamples, Nsamples+Nburnin)
        end_time=time.time()
        print("Number of total samples:", Nwalkers*Nsamples)
        print("Run time [s]:", end_time-start_time)

        return sampler

    def _lnprior(self, theta, i=0):

        Ncom=self.Config.getpar('Ncom')

        lp = 0.  #initialize log prior
        logn, logtemp, logomega = theta # unpack the model parameters from the list #logt                                            
        if(Ncom==1):
            lognmin = self.Config.getpar('lognmin')  # lower range of prior                                                        
            lognmax = self.Config.getpar('lognmax')  # upper range of prior                                                        
            logtmin = self.Config.getpar('logtmin')  #logt
            logtmax = self.Config.getpar('logtmax')  #logt
            logomegamin = self.Config.getpar('logomegamin')
            logomegamax = self.Config.getpar('logomegamax')
        if(Ncom>1):
            lognmin = self.Config.getpar('lognmin_'+str(i))  # lower range of prior                                                        
            lognmax = self.Config.getpar('lognmax_'+str(i))  # upper range of prior                                                        
            logtmin = self.Config.getpar('logtmin_'+str(i)) #logt
            logtmax = self.Config.getpar('logtmax_'+str(i)) #logt
            logomegamin = self.Config.getpar('logomegamin_'+str(i))
            logomegamax = self.Config.getpar('logomegamax_'+str(i))

        #First parameter: logn - uniform prior
        lp = 0. if lognmin < logn < lognmax else -np.inf 

        #Second parameter: log temperature - uniform prior
        lpt = 0. if logtmin < logtemp < logtmax else -np.inf  #logt
        lp += lpt #Add log prior due to temperature to lp due to logn

        #Third parameter: log Omega - uniform prior
        lpo = 0. if logomegamin < logomega < logomegamax else -np.inf
        lp += lpo #Add log prior due to omega to lp due to temperature,logn

        return lp

    def _lnprior_multicom(self, theta):
        Ncom=self.Config.getpar('Ncom') #Get number of components from config

        if(Ncom==1): #If only one component, just compute prior and return
            mytheta=theta
            lp=self._lnprior(mytheta)

        if(Ncom>1): #If >1 component, loop through components and add fluxes
            for i in np.arange(Ncom):
                mytheta=theta[3*i:3*i+3]
                mylp=self._lnprior(mytheta,i=i)
                if (i==0): lp=mylp
                else: lp+=mylp
        return lp

    def _lnlikelihood(self, theta):
        md = self._compute_fluxes_multicom(theta)  #model
        data=self.LineData.lineflux
        sigma=self.LineData.lineflux_err
        lnlike = -0.5*np.sum(((md - data)/sigma)**2)
        
        return lnlike

    def _lnposterior(self,theta):
        lp = self._lnprior_multicom(theta)

        if not np.isfinite(lp):
            return -np.inf

        return lp + self._lnlikelihood(theta)

    def _compute_fluxes_multicom(self,theta):
        Ncom=self.Config.getpar('Ncom') #Get number of components from config

        if(Ncom==1): #If only one component, just compute fluxes and return
            mytheta=theta
            lineflux=self._compute_fluxes(mytheta)

        if(Ncom>1): #If >1 component, loop through components and add fluxes
            for i in np.arange(Ncom):
                mytheta=theta[3*i:3*i+3]
                mylineflux=self._compute_fluxes(mytheta)
                if (i==0): lineflux=mylineflux
                else: lineflux+=mylineflux                                

        return lineflux

    def _compute_fluxes(self,theta):
        logn, logtemp, logomega = theta    #unpack parameters  #logt
        temp=10**logtemp  #logt
        omega=10**logomega
        n_col=10**logn
        si2jy=1e26   #SI to Jy flux conversion factor

#If local velocity field is not given, assume sigma given by thermal velocity

        mu=u.value*self.LineData.molmass
        deltav=np.sqrt(k_B.value*temp/mu)   #m/s 

#Use line_ids to extract relevant HITRAN data
        wn0=self.LineData.wn0
        aup=self.LineData.aup
        eup=self.LineData.eup
        gup=self.LineData.gup
        eup_k=self.LineData.eup_k
        elower=self.LineData.elower 

#Compute partition function
        q=self._get_partition_function(temp)
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

        pre_val = 2*h.value*c.value*wn0**3.
        for i in range(nlines):
            f_arr[i, :] = pre_val[i] / (np.exp(wnfactor[i]) - 1.0e0) * (1 - np.exp(-tau[i, :])) * si2jy * omega

        lineflux_jykms = np.sum(f_arr, axis=1) * dvel
        lineflux = lineflux_jykms * 1e-26 * 1. * 1e5 * (1. / (w0 * 1e-4))  # mks

#        for i in range(nlines):  #Loop is time-consuming.  Maybe it can be removed somehow?
#            f_arr[i,:]=2*h.value*c.value*wn0[i]**3./(np.exp(wnfactor[i])-1.0e0)*(1-np.exp(-tau[i,:]))*si2jy*omega
#            lineflux_jykms=np.sum(f_arr[i,:])*dvel
#            lineflux[i]=lineflux_jykms*1e-26*1.*1e5*(1./(w0[i]*1e-4))    #mks

        return lineflux
#------------------------------------------------------------------------------
    def _get_partition_function(self,temp):
    #Loop through each unique identifier
    #For each unique identifier, assign q values accordingly
        q=np.zeros(self.LineData.nlines)
        for myunique_id in self.LineData.unique_globals:
            myq=self.LineData.qdata_dict[str(myunique_id)][int(temp)-1]  #Look up appropriate q value
            mybool=(self.LineData.global_id == myunique_id)              #Find where global identifier equals this one
            q[mybool]=myq                                      #Assign q values where global identifier equals this one
        return q
#------------------------------------------------------------------------------------                                     
class LineData():
    def __init__(self,data):
        self.wn0=data['wn']*1e2 # now m-1
        self.aup=data['a']
        self.eup=(data['elower']+data['wn'])*1e2 #now m-1
        self.gup=data['gup']
        self.eup_k=data['eup_k']
        self.elower=data['elower']
        self.molec_id=data['molec_id']
        self.local_iso_id=data['local_iso_id']
#        self.qpp = data['Qpp_HITRAN']
#        self.qp = data['Qp_HITRAN']
#        self.vp = data['Vp_HITRAN'] 
#        self.vpp = data['Vpp_HITRAN']
        self.lineflux=data['lineflux']
        self.lineflux_err=data['lineflux_err']
        self.nlines = len(self.lineflux)
        self.global_id=self._return_global_ids()  #Determine HITRAN global ids (molecule + isotope) for each line
        self.molmass=self._return_molmasses()  #Get molecular mass
        self.unique_globals = np.unique(self.global_id)
        self.qdata_dict=self._get_qdata()
#---------------------
    #Returns HITRAN molecular masses for all lines
    def _return_molmasses(self):
        molmass_arr = np.array([get_molmass(translate_molecule_identifier(self.molec_id[i]), isotopologue_number=self.local_iso_id[i]) for i in np.arange(self.nlines)])
        return molmass_arr
#---------------------
    #Returns HITRAN global IDs for all lines
    def _return_global_ids(self):
        global_id = np.array([get_global_identifier(translate_molecule_identifier(self.molec_id[i]), isotopologue_number=self.local_iso_id[i]) for i in np.arange(self.nlines)])
        return global_id
#------------------------------------------------------------------------------------                                    
    def _get_qdata(self):
        id_array=self.unique_globals
        q_dict={}
        for myid in id_array:
            qurl='https://hitran.org/data/Q/'+'q'+str(myid)+'.txt'
            handle = urllib.request.urlopen(qurl)
            qdata = pd.read_csv(handle,sep=' ',skipinitialspace=True,names=['temp','q'],header=None)
            q_dict.update({str(myid):qdata['q']})
        return q_dict

#------------------------------------------------------------------------------------                                     
    def rot_diagram(self,units='mks',modelfluxes=None):
        x=self.eup_k
        mywn0=self.wn0
        y=np.log(self.lineflux/(mywn0*self.gup*self.aup))  #All mks, so wn in m^-1
        if(units=='cgs'):
            y=np.log(1000.*self.lineflux/((self.wn0*1e-2)*self.gup*self.aup))   #All cgs
        if(units=='mixed'):
            y=np.log(self.lineflux/((self.wn0*1e-2)*self.gup*self.aup))
        rot_dict={'x':x,'y':y,'units':units}
        if(modelfluxes is not None):
            rot_dict['modely']=np.log(modelfluxes/(mywn0*self.gup*self.aup))  #All mks, so wn in m^-1
            if(units=='cgs'):
                rot_dict['modely']=np.log(modelfluxes*1000./(self.wn0*1e-2*self.gup*self.aup))  #All cgs
            if(units=='mixed'):
                rot_dict['modely']=np.log(modelfluxes/(self.wn0*1e-2*self.gup*self.aup))  #Mixed units

        return rot_dict
#------------------------------------------------------------------------------------                                     
