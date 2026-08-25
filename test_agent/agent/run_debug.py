import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent import main
main()
