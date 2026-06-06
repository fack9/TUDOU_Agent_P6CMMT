from PIL import Image, ImageEnhance, ImageOps
try:
    from .palettes import PALETTES, build_palette_image
except ImportError:
    from palettes import PALETTES, build_palette_image
PRESETS = {'arcade': {'contrast': 1.8, 'color': 1.5, 'sharpness': 1.2, 'posterize_bits': 5, 'block': 8, 'palette': 16}, 'snes': {'contrast': 1.6, 'color': 1.4, 'sharpness': 1.2, 'posterize_bits': 6, 'block': 4, 'palette': 32}, 'nes': {'contrast': 1.5, 'color': 1.4, 'sharpness': 1.2, 'posterize_bits': 6, 'block': 8, 'palette': 'NES'}, 'gameboy': {'contrast': 1.5, 'color': 1.0, 'sharpness': 1.2, 'posterize_bits': 6, 'block': 8, 'palette': 'GAMEBOY_ORIGINAL'}, 'gameboy_pocket': {'contrast': 1.5, 'color': 1.0, 'sharpness': 1.2, 'posterize_bits': 6, 'block': 8, 'palette': 'GAMEBOY_POCKET'}, 'pico8': {'contrast': 1.6, 'color': 1.3, 'sharpness': 1.2, 'posterize_bits': 6, 'block': 6, 'palette': 'PICO_8'}, 'c64': {'contrast': 1.6, 'color': 1.3, 'sharpness': 1.2, 'posterize_bits': 6, 'block': 8, 'palette': 'C64'}, 'apple2': {'contrast': 1.8, 'color': 1.4, 'sharpness': 1.2, 'posterize_bits': 5, 'block': 10, 'palette': 'APPLE_II_HI'}, 'teletext': {'contrast': 1.8, 'color': 1.5, 'sharpness': 1.2, 'posterize_bits': 5, 'block': 10, 'palette': 'TELETEXT'}, 'mspaint': {'contrast': 1.6, 'color': 1.4, 'sharpness': 1.2, 'posterize_bits': 6, 'block': 8, 'palette': 'MICROSOFT_WINDOWS_PAINT'}, 'mono_green': {'contrast': 1.8, 'color': 0.0, 'sharpness': 1.2, 'posterize_bits': 5, 'block': 6, 'palette': 'MONO_GREEN'}, 'mono_amber': {'contrast': 1.8, 'color': 0.0, 'sharpness': 1.2, 'posterize_bits': 5, 'block': 6, 'palette': 'MONO_AMBER'}, 'neon': {'contrast': 1.8, 'color': 1.6, 'sharpness': 1.2, 'posterize_bits': 5, 'block': 6, 'palette': 'NEON_CYBER'}, 'pastel': {'contrast': 1.2, 'color': 1.3, 'sharpness': 1.1, 'posterize_bits': 6, 'block': 6, 'palette': 'PASTEL_DREAM'}}

def pixel_art(input_path, output_path, preset='arcade', **overrides):
    if preset not in PRESETS:
        raise ValueError(f'Unknown preset {preset!r}. Choose from: {sorted(PRESETS)}')
    cfg = {**PRESETS[preset], **overrides}
    img = Image.open(input_path).convert('RGB')
    img = ImageEnhance.Contrast(img).enhance(cfg['contrast'])
    img = ImageEnhance.Color(img).enhance(cfg['color'])
    img = ImageEnhance.Sharpness(img).enhance(cfg['sharpness'])
    img = ImageOps.posterize(img, cfg['posterize_bits'])
    w, h = img.size
    block = cfg['block']
    small = img.resize((max(1, w // block), max(1, h // block)), Image.NEAREST)
    pal = cfg['palette']
    if isinstance(pal, str):
        pal_img = build_palette_image(pal)
        quantized = small.quantize(palette=pal_img, dither=Image.FLOYDSTEINBERG)
    else:
        quantized = small.quantize(colors=int(pal), dither=Image.FLOYDSTEINBERG)
    result = quantized.resize((w, h), Image.NEAREST)
    result.save(output_path, 'PNG')
    return result

def main():
    import argparse
    p = argparse.ArgumentParser(description='Convert image to pixel art.')
    p.add_argument('input')
    p.add_argument('output')
    p.add_argument('--preset', default='arcade', choices=sorted(PRESETS))
    p.add_argument('--palette', default=None, help=f'Override palette: int or name from {sorted(PALETTES)}')
    p.add_argument('--block', type=int, default=None)
    args = p.parse_args()
    overrides = {}
    if args.palette is not None:
        try:
            overrides['palette'] = int(args.palette)
        except ValueError:
            overrides['palette'] = args.palette
    if args.block is not None:
        overrides['block'] = args.block
    pixel_art(args.input, args.output, preset=args.preset, **overrides)
    print(f'Wrote {args.output}')
if __name__ == '__main__':
    main()
