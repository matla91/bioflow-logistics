<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}" @class(['dark' => auth()->check() || ($appearance ?? 'system') === 'dark']) @if(auth()->check()) data-theme="dark" @endif>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">

        {{-- The authenticated demo is dark before first paint; guests retain their preference. --}}
        <script>
            (function() {
                const appearance = '{{ $appearance ?? "system" }}';

                if (document.documentElement.dataset.theme !== 'dark' && appearance === 'system') {
                    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

                    if (prefersDark) {
                        document.documentElement.classList.add('dark');
                    }
                }
            })();
        </script>

        {{-- Inline style to set the HTML background color based on our theme in app.css --}}
        <style>
            html {
                background-color: oklch(1 0 0);
            }

            html.dark {
                background-color: var(--assessment-bg, oklch(0.145 0 0));
                color-scheme: dark;
            }
        </style>

        <link rel="icon" href="/brand/smartflow-mark.png" type="image/png">
        <link rel="apple-touch-icon" href="/brand/smartflow-mark.png">

        @fonts

        @vite(['resources/css/app.css', 'resources/js/app.ts', "resources/js/pages/{$page['component']}.vue"])
        <x-inertia::head>
            <title>Smartflow</title>
        </x-inertia::head>
    </head>
    <body class="font-sans antialiased">
        <x-inertia::app />
    </body>
</html>
