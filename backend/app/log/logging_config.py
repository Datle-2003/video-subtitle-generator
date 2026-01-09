import logging

def setup_logging(log_file: str = "app.log"):
    root_logger = logging.getLogger()
    if not root_logger.hasHandlers():
        # file
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        fh.setLevel(logging.INFO) 
        root_logger.addHandler(fh)
        
        # console
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        sh.setLevel(logging.WARNING) 
        root_logger.addHandler(sh)
        
        root_logger.setLevel(logging.INFO) 