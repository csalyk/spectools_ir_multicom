from setuptools import setup
setup(
    name = 'spectools-ir-multicom',
    packages = ['spectools_ir_multicom','spectools_ir_multicom.slabspec','spectools_ir_multicom.flux_calculator','spectools_ir_multicom.utils','spectools_ir_multicom.slab_fitter'],
    version = '0.1.0',
    description = 'Tools for analysis and modeling of IR spectra with multi-component models',
    long_description_content_type="text/markdown",
    long_description=open('README.md').read(),
    author='Colette Salyk',
    author_email='cosalyk@vassar.edu',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering :: Astronomy',
        ],
    url='https://github.com/csalyk/spectools_ir_multicom',
    include_package_data=True,    
    package_data={'': ['*.json']},
    install_requires=[
        'astropy>=4.2',
        'emcee>=3.0',
        'numpy>=1',
        'pandas>=0.24',
        'corner>=2.1',
        'matplotlib>=3',
        'astroquery>0.4',
        'scipy>=1.2',
        'IPython>=7.4',
    ]
) 
