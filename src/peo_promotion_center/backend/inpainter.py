"""Módulo de inpainting para borrado y reconstrucción de regiones de imagen."""

import torch
from PIL import Image
from simple_lama_inpainting import SimpleLama

_lama: SimpleLama | None = None


def get_lama() -> SimpleLama:
    """
    Devuelve la instancia singleton de SimpleLama, inicializándola si es necesario.

    El modelo (~200 MB) se descarga automáticamente en ~/.cache/simple-lama
    la primera vez y queda cacheado para ejecuciones posteriores.

    La versión instalada de simple-lama-inpainting llama a torch.jit.load sin
    map_location, lo que falla cuando el modelo fue serializado en CUDA y el
    entorno no tiene soporte CUDA completo. Se parchea temporalmente para
    forzar la carga en CPU.

    Returns:
        Instancia compartida de SimpleLama.
    """
    global _lama
    if _lama is None:
        _original_jit_load = torch.jit.load

        def _cpu_jit_load(f, map_location: str = "cpu", **kwargs):
            return _original_jit_load(f, map_location=map_location, **kwargs)

        torch.jit.load = _cpu_jit_load  # type: ignore[assignment]
        try:
            _lama = SimpleLama(device=torch.device("cpu"))
        finally:
            torch.jit.load = _original_jit_load  # type: ignore[assignment]
    return _lama


def inpaint(image: Image.Image, mask: Image.Image) -> Image.Image:
    """
    Borra la región marcada en mask y rellena con LaMa.

    Args:
        image: Imagen RGB a procesar (en la resolución final del formato).
        mask:  Imagen de máscara; blanco (255) = zona a borrar.

    Returns:
        Imagen RGB con la región borrada y reconstruida.
    """
    return get_lama()(image, mask.convert("L"))
