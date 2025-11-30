from setuptools import setup, find_packages

setup(
    name='ai-act-check',
    version='0.1.0',
    description='Static scanner and Annex IV drafter for EU AI Act compliance (prototype)',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'python-dotenv',
        'openai'
    ],
    entry_points={
        'console_scripts': [
            'ai-act-check=ai_act_check.cli:main'
        ]
    },
    python_requires='>=3.8'
)
