#!/usr/bin/env python3
"""The reviewer's judgement on each design's code, kept in one place, written out as evidence/11-code-verdict.json in every design's folder.

For each design the reviewer reads the candidates of the search (evidence/10-candidates.json, shown by review_candidates.py)
and records here: each repository worth naming with a verdict (official: the authors' own code for this paper; unofficial
reimplementation; third-party tool the paper names; not the design's code) and the reason; the code status of the design
(released with an open licence, released without a licence, on request, not found); and whether there is any sign that code
ever existed. Repositories found only by name and ruled out as a group (reading lists, unrelated projects) are summarised in
`ruled_out` rather than listed one by one; every one of them stays in 10-candidates.json.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/code_verdicts.py [<id> ...]
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import load_designs, save_json, now   # noqa: E402

LISTS = 'reading lists and paper digests that cite the paper (awesome-lists, survey collections, daily arXiv feeds, metadata dumps)'
NONE_FOUND = 'no link in the paper; nothing in the Papers with Code archive, Hugging Face Papers, DataCite, Zenodo or Scholexplorer; ' \
             'no repository by the authors or naming the design on GitHub, GitLab, Gitee or Software Heritage'

V = {
    'N004': {'status': 'not found', 'ever': 'no sign that code was ever published',
             'repos': [{'repo': 'https://github.com/Dyagaravindher/BLOCKCHAIN-BASED-FEDERATED-LEARNING-WITH-SMPC-MODEL-VERIFICATION-AGAINST-POISONING-ATTACK.',
                        'verdict': "not the design's code",
                        'reason': 'named after the paper, but a Django web-application template (user and admin pages, migrations of 2019, a healthcare CSV); '
                                  'no federated learning, SMPC or blockchain code; owner is not an author; no licence'}],
             'ruled_out': LISTS, 'note': NONE_FOUND + '. The arXiv preprint (2304.13360) lists no code.'},
    'N007': {'status': 'not found', 'ever': 'no sign that code was ever published',
             'repos': [{'repo': 'https://github.com/xiaosongz/neuralnilm', 'verdict': "not the design's code",
                        'reason': 'an account named like an author (Xiaosong Zhang); the repository is energy disaggregation (2017), unrelated'}],
             'ruled_out': LISTS, 'note': NONE_FOUND},
    'N008': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [], 'ruled_out': LISTS, 'note': NONE_FOUND},
    'N009': {'status': 'not found', 'ever': 'no sign that code was ever published',
             'repos': [{'repo': 'https://github.com/Yu-shui/PaddleVideo', 'verdict': "not the design's code",
                        'reason': 'an account named like an author (Shui Yu); a copy of the PaddleVideo toolkit, unrelated'}],
             'ruled_out': LISTS, 'note': NONE_FOUND},
    'N010': {'status': 'not found', 'ever': 'no sign that code was ever published',
             'repos': [{'repo': 'https://github.com/msrocean/Latent-Replay', 'verdict': "not the design's code",
                        'reason': 'an account named like an author (Mohammad Saidur Rahman); continual-learning code (2024), unrelated'}],
             'ruled_out': LISTS + '; the Scholexplorer link is the arXiv record of the preprint',
             'note': NONE_FOUND + '. The arXiv preprint (2304.12889) lists no code.'},
    'N011': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
             'ruled_out': LISTS + '; repositories of an unrelated account named lpbfly', 'note': NONE_FOUND},
    'N012': {'status': 'not found', 'ever': 'no sign that code was ever published',
             'repos': [{'repo': 'https://github.com/androlo/standard-contracts', 'verdict': 'third-party tool named in the paper',
                        'reason': 'Solidity contracts with cryptographic routines (MIT), linked on page 8 as a building block; not the design'},
                       {'repo': 'https://github.com/ofek/coincurve', 'verdict': 'third-party tool named in the paper',
                        'reason': 'Python library for secp256k1 elliptic-curve operations (Apache-2.0), linked on page 8; not the design'}],
             'ruled_out': LISTS, 'note': NONE_FOUND},
    'N013': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [], 'ruled_out': LISTS, 'note': NONE_FOUND},
    'N014': {'status': 'not found', 'ever': 'no sign that the code of this design was published',
             'repos': [{'repo': 'https://github.com/harshkasyap/DecFL', 'verdict': "author's related code",
                        'reason': "the first author's own repository (2022) for an earlier design, the blockchain-assisted reputation-aware "
                                  "decentralised FL framework that N014 compares against; not N014's Fabric and Kafka design; no licence"},
                       {'repo': 'https://github.com/harshkasyap', 'verdict': "not the design's code",
                        'reason': "the first author's account, listed in full (96 repositories): no repository for this design; the "
                                  "federated-learning repositories are forks of others' work or code of other papers"}],
             'ruled_out': LISTS + '; repositories named VPSA... found by name in Software Heritage, unrelated', 'note': NONE_FOUND},
    'N015': {'status': 'not found', 'ever': 'no sign that code was ever published',
             'repos': [{'repo': 'https://github.com/leix28/privacy', 'verdict': "not the design's code",
                        'reason': 'an account named like an author (Lei Xu); a copy of a differential-privacy training library, unrelated to the design'}],
             'ruled_out': 'other repositories of accounts named like the authors (protein structure, reinforcement learning)', 'note': NONE_FOUND},
    'N016': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
             'ruled_out': LISTS + '; repositories of accounts named like the authors (Jing Wang, Jie Zhang): visual odometry, routing, FedAvg and other federated-learning papers\' code, none of them this design',
             'note': NONE_FOUND},
    'N017': {'status': 'not found', 'ever': 'no sign that the code of this design was published',
             'repos': [{'repo': 'https://github.com/hanbaofu/FISCO_BCOS_FL', 'verdict': "author's related code",
                        'reason': "the first author's own repository (2025, GPL-3.0): a hierarchical master-and-slave-group blockchain FL framework on FISCO-BCOS "
                                  "with MNIST and CIFAR; its Paillier code is FISCO-BCOS's built-in precompile; no Shamir masking, no Algorand-style committee, "
                                  "no California Housing regression, so not this design"},
                       {'repo': 'https://github.com/hanbaofu', 'verdict': "not the design's code",
                        'reason': "the first author's account, listed in full: the other blockchain-FL repositories are forks of others' work (VeryFL, "
                                  "Blockchain-enabled Server-less FL) or the code of another paper (SustainableIncentiveFL)"}],
             'ruled_out': 'twenty repositories named PBFL or alike by other people (PBFL is a common acronym: other papers, a trading-label method, unrelated tools)',
             'note': NONE_FOUND},
    'N018': {'status': 'not found', 'ever': 'no sign that the code of this design was published',
             'repos': [{'repo': 'https://github.com/shaoxiongji/federated-learning', 'verdict': 'third-party tool named in the paper',
                        'reason': 'the PyTorch federated-learning code (MIT) the paper names on page 10 as its base; a building block for implementing the design, not the design'},
                       {'repo': 'https://github.com/data61/python-paillier', 'verdict': 'third-party tool named in the paper',
                        'reason': 'the Paillier library (GPL-3.0) the paper names on page 10; a building block, not the design',
                        'licence_read': 'GPL-3.0'},
                       {'repo': 'https://github.com/lhysgithub', 'verdict': "not the design's code",
                        'reason': 'an account named like an author (Hongyi Liu): copies of attack libraries (GradAttack, backdoors101) and code of other papers'}],
             'ruled_out': LISTS, 'note': NONE_FOUND},
    'N019': {'status': 'released, no licence', 'ever': 'published by the first author on GitHub (created 27 October 2025, last push 17 May 2026); not linked in the paper',
             'repos': [{'repo': 'https://github.com/hujunxu/HHB-FL', 'verdict': 'official',
                        'reason': "the account hujunxu matches the first author (Junxu Hu); the repository is named after the design and its README "
                                  "describes it (Paillier and CKKS, Laplace DP with L1 clipping, a smart-contract aggregator, AIS data from NOAA, "
                                  "Docker with one contract and ten clients, attack modules); found by the GitHub search for the design's name; no licence file"}],
             'ruled_out': 'a Flipper Zero app named HHB, unrelated', 'note': 'GitHub repository search by the design\'s name'},
    'N020': {'status': 'not found', 'ever': 'no sign that code was ever published',
             'repos': [{'repo': 'https://github.com/huangl223/li_new', 'verdict': "not the design's code",
                        'reason': 'an account named like an author (Huang Li); a fork of a portfolio-website template'},
                       {'repo': 'https://github.com/pipefitter-io/rbpfl', 'verdict': "not the design's code",
                        'reason': 'named rbpfl, but a Ruby pipe-and-filter library'}],
             'ruled_out': '', 'note': NONE_FOUND},
    'n0207': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': LISTS + ' (autonomous-driving and edge-AI lists among them)', 'note': NONE_FOUND},
    'N021': {'status': 'not found', 'ever': 'no sign that code was ever published; the publisher\'s one supplementary item is a PDF (filed in evidence/supplementary/)',
             'repos': [{'repo': 'https://github.com/yiminyu', 'verdict': "not the design's code",
                        'reason': 'an account named like an author (Yimin Yu): Ethereum financial-instrument and data-market contracts of 2018, unrelated'}],
             'ruled_out': '', 'note': NONE_FOUND + '; IEEE Xplore lists one supplementary PDF, no code'},
    'n0414': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': 'repositories of accounts named like the authors (a university blockchain course, interatomic-potential learning, study notes), unrelated; '
                           'the paper names ZoKrates as a tool', 'note': NONE_FOUND},
    'n0763': {'status': 'not found', 'ever': 'no sign that code was ever published',
              'repos': [{'repo': 'https://github.com/zalandoresearch/fashion-mnist', 'verdict': "not the design's code",
                         'reason': 'the Fashion-MNIST dataset repository, linked on page 16 as the data source'}],
              'ruled_out': LISTS + '; a privacy-preserving ML reading list on an account named like an author (Tengfei Liu)', 'note': NONE_FOUND},
    'n1640': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': 'a daily arXiv digest', 'note': NONE_FOUND},
    'n1749': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': 'one unrelated repository found by title words', 'note': NONE_FOUND},
    'n2405': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': LISTS + ' (decentralised-web and self-hosting lists among them)', 'note': NONE_FOUND},
    'n2438': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': 'four unrelated repositories found by name in the code search', 'note': NONE_FOUND},
    'n2723': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': LISTS + '; unrelated web3 and blockchain projects, among them a generic blockchain-FL project (narasimhabtech27-commits/bfl-project, 2026) that does not name or cite the paper', 'note': NONE_FOUND},
    'n2912': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': LISTS + ' (network, satellite and communication paper lists, daily arXiv feeds)', 'note': NONE_FOUND},
    'n3102': {'status': 'not found', 'ever': 'no sign that code was ever published; the paper states its data are available on request',
              'repos': [], 'ruled_out': 'three unrelated threat-intelligence and phishing projects found by name', 'note': NONE_FOUND},
    'n3348': {'status': 'not found', 'ever': 'no sign that code was ever published',
              'repos': [{'repo': 'https://github.com/marcellomaugeri/flare-FL', 'verdict': "not the design's code",
                         'reason': 'named after the Flare blockchain: a 2025 hackathon project for federated learning on the Flare chain, not this design'},
                        {'repo': 'https://github.com/FondH/SafeGrad', 'verdict': "not the design's code",
                         'reason': 'a different paper of the same name (gradient surgery for safe LLM fine-tuning)'}],
              'ruled_out': LISTS + '; other repositories named FLARE, SafeGrad or EconChain, unrelated (FLARE, SafeGrad and EconChain are common names)',
              'note': NONE_FOUND},
    'n3686': {'status': 'not found', 'ever': 'no sign that code was ever published',
              'repos': [{'repo': 'https://github.com/LiYangHart', 'verdict': "not the design's code",
                         'reason': "an account named like an author: Li Yang of Ontario Tech University, whose MIT intrusion-detection repositories are his own "
                                   "papers'; the paper's co-author Yang Li is at Shihezi University (ORCID 0000-0002-4268-4004), a different person"}],
              'ruled_out': 'cybersecurity reading lists and unrelated intrusion-detection projects found by title words', 'note': NONE_FOUND},
    'n3813': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': 'blockchain clients and proof-of-authority projects found by the name PoA-X, unrelated', 'note': NONE_FOUND},
    'n3855': {'status': 'not found', 'ever': 'no sign that code was ever published',
              'repos': [{'repo': 'https://github.com/BoAi01/Duckietown-RL', 'verdict': "not the design's code",
                         'reason': 'an account named like an author (Bo Ai): sim-to-real reinforcement learning for vehicle control, another paper'}],
              'ruled_out': LISTS + "; a personal website citing many papers", 'note': NONE_FOUND},
    'n3910': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': 'a privacy-computing reading list; the paper names ZoKrates and Hyperledger Fabric as tools', 'note': NONE_FOUND},
    'O043': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
             'ruled_out': LISTS + ' (O043 is widely cited: 37 more lists and digests)', 'note': NONE_FOUND},
    'O108': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
             'ruled_out': 'daily arXiv feeds, metadata dumps and unrelated projects found by the names zkFDL and zkDFL',
             'note': NONE_FOUND + '. Its arXiv preprint (2312.04579, found through Semantic Scholar) has no code on Hugging Face Papers or in the Papers with Code archive.'},
    'p4875': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': LISTS, 'note': NONE_FOUND},
    'r0043': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': 'a review\'s reading notes (MartinNoc/PPDL-Review), awesome-lists and digests that cite the paper', 'note': NONE_FOUND},
    'r0159': {'status': 'on request', 'ever': 'not published; the paper offers the code on request (page 16) and the data on request (page 17)',
              'repos': [], 'ruled_out': LISTS + '; repositories of accounts named like the authors (copies of torchmetrics and MXNet, '
              'reinforcement-learning and routing code of other papers), unrelated', 'note': NONE_FOUND},
    'r0202': {'status': 'not found', 'ever': 'no sign that code was ever published',
              'repos': [{'repo': 'https://github.com/Ashvin-Gupta/HealthSentinel', 'verdict': "not the design's code",
                         'reason': 'gone from GitHub; Software Heritage holds a copy whose last commit (29 December 2021, a login-page layout change) predates the paper by years'},
                        {'repo': 'https://github.com/NicoBSU/HealthSentinel', 'verdict': "not the design's code",
                         'reason': 'gone from GitHub; Software Heritage found nothing when it visited (7 August 2024), so no copy exists'}],
              'ruled_out': 'eleven other repositories named HealthSentinel (a common name: epidemic dashboards, vital-sign displays, health prediction apps); '
                           'none of their READMEs mentions federated learning, zero-knowledge proofs, the neuro-symbolic model or CICIoMT2024',
              'note': NONE_FOUND},
    'r0230': {'status': 'not found', 'ever': 'no sign that code was ever published; the paper offers its data on request (page 17)', 'repos': [],
              'ruled_out': 'about thirty repositories named BFLP, almost all coursework of an IT bootcamp of that name or unrelated web pages; none mentions '
                           'federated learning, blockchain or vehicles', 'note': NONE_FOUND},
    'r0252': {'status': 'not found', 'ever': 'no sign that code was ever published', 'repos': [],
              'ruled_out': 'nothing found by any source', 'note': NONE_FOUND},
    'r0284': {'status': 'not found', 'ever': 'no sign that code was ever published',
              'repos': [{'repo': 'https://github.com/SLJME42/2RCECM', 'verdict': "not the design's code",
                         'reason': 'named 2RCECM: parameter identification for a two-RC equivalent-circuit battery model, another paper'}],
              'ruled_out': 'reading lists and content-management projects found by the name RCECM', 'note': NONE_FOUND},
    'r0323': {'status': 'not found', 'ever': 'no sign that code was ever published',
              'repos': [{'repo': 'https://github.com/wensy18/FedShard', 'verdict': "not the design's code",
                         'reason': 'a different paper of the same name: FedShard (AAAI 2026) on federated unlearning, by Wen Siyuan of HKUST (Guangzhou); '
                                   'not r0323 (Ma et al. 2026, sharded Fabric-based FL with local DP and distillation)'}],
              'ruled_out': LISTS + '; repositories of an account named like an author (knowledge graphs for drug discovery, PyKale)', 'note': NONE_FOUND},
    'r0355': {'status': 'not found', 'ever': 'no sign that the code of this design was published',
              'repos': [{'repo': 'https://github.com/Prasanjit-Dey', 'verdict': "not the design's code",
                         'reason': "the first author's account, listed in full (49 repositories): air-pollution forecasting, time-series and other "
                                   "projects; nothing on twin SVMs, decision trees, Paillier or blockchain; the 2021 data-preprocessing repository is a CSV "
                                   "clean-up project, not the design"}],
              'ruled_out': 'twin-SVM and semi-supervised learning repositories of others found by the name DT-TSVM', 'note': NONE_FOUND},
    'n2721': {'status': 'released, open licence', 'ever': 'published by the authors and linked in the paper (page 11)',
              'repos': [{'repo': 'https://github.com/CaixiangFan/zkpet', 'verdict': 'official',
                         'reason': 'linked in the paper (page 11); owner is the first author; README names the design',
                         'pin': 'e96153d', 'pin_reason': 'the commit reproduced in experiments/zkpet (five runs, 19 October 2026)'}],
              'ruled_out': LISTS + '; course projects on an account named like a co-author (Sohrabbeig); other repositories named zkpet (a hackathon project, unrelated tools)',
              'note': 'the paper\'s own link; the search found no other copy'},
    'n3299': {'status': 'released, no licence', 'ever': 'published by the authors and linked in the paper (page 2)',
              'repos': [{'repo': 'https://github.com/Aw-creat/Fed-EALE', 'verdict': 'official',
                         'reason': 'linked in the paper (page 2); README cites the paper\'s title and names the design'}],
              'ruled_out': LISTS + '; three reading lists and a huge word-list profile README that happen to name the authors', 'note': 'the paper\'s own link; the search found no other copy and no licence anywhere'},
    'n3378': {'status': 'released, open licence', 'ever': 'published by the authors and linked in the paper (page 41)',
              'repos': [{'repo': 'https://github.com/wisamalwashYildiz/FL-BC-IDS', 'verdict': 'official',
                         'reason': 'linked in the paper (page 41); owner is the first author; README cites the title and names the design',
                         'pin': '0bd5732', 'pin_reason': 'the commit reproduced in experiments/fl-bc-ids (four runs and the scale sweep, 19-20 October 2026)'}],
              'ruled_out': LISTS + '; the reviewer\'s own release repository (shakir1311), excluded', 'note': 'the paper\'s own link'},
}


def main():
    ids = set(sys.argv[1:])
    n = 0
    for d in load_designs():
        if d['id'] not in V or (ids and d['id'] not in ids):
            continue
        v = V[d['id']]
        save_json(d['folder'] / 'evidence' / '11-code-verdict.json', {
            'about': "The reviewer's judgement on the design's code, from the search's candidates (10-candidates.json) and the "
                     "repositories' own pages; kept in scripts/design_eval/code_verdicts.py.",
            'made': now(), 'reviewer': 'Claude, for the author to check', 'code_status': v['status'],
            'ever_published': v['ever'], 'repositories': v['repos'], 'ruled_out_as_a_group': v.get('ruled_out', ''),
            'how_searched': v.get('note', '')})
        n += 1
    print(f'{n} code verdicts written')


if __name__ == '__main__':
    main()
