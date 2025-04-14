from abc import ABC, abstractmethod

class BaseProcessor(ABC):
    """Clase base para procesadores de imágenes"""
    
    @abstractmethod
    def initialize(self):
        """Inicializa recursos necesarios"""
        pass
    
    @abstractmethod
    def process(self, image, zones):
        """Procesa una imagen con zonas definidas"""
        pass
