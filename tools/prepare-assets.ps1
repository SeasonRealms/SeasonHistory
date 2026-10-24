param([string]$SourceRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent))
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$target = Join-Path (Split-Path $PSScriptRoot -Parent) 'docs/assets/img'
[void][System.IO.Directory]::CreateDirectory($target)
$manifest = [System.Collections.Generic.List[object]]::new()

# 从用户提供的原图导出网页尺寸，不修改任何来源素材。
function Export-Art([string]$Source, [string]$Name, [int]$Width, [int]$Quality = 85, [switch]$Circle) {
    $image = [System.Drawing.Image]::FromFile((Join-Path $SourceRoot $Source))
    $bitmap = $null; $graphics = $null; $parameters = $null; $clip = $null
    try {
        $w = [Math]::Min($Width, $image.Width)
        $h = [int][Math]::Round($image.Height * $w / $image.Width)
        $bitmap = [System.Drawing.Bitmap]::new($w, $h)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        if ($Circle) {
            $graphics.Clear([System.Drawing.Color]::Transparent)
            $clip = [System.Drawing.Drawing2D.GraphicsPath]::new()
            $clip.AddEllipse(1, 1, ($w - 2), ($h - 2))
            $graphics.SetClip($clip)
        }
        $graphics.DrawImage($image, 0, 0, $w, $h)
        $destination = Join-Path $target $Name
        if ($Name.EndsWith('.png')) {
            $bitmap.Save($destination, [System.Drawing.Imaging.ImageFormat]::Png)
        } else {
            $codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object MimeType -eq 'image/jpeg'
            $parameters = [System.Drawing.Imaging.EncoderParameters]::new(1)
            $parameters.Param[0] = [System.Drawing.Imaging.EncoderParameter]::new([System.Drawing.Imaging.Encoder]::Quality, [long]$Quality)
            $bitmap.Save($destination, $codec, $parameters)
        }
        $manifest.Add([ordered]@{file=$Name; source=$Source.Replace('\','/'); width=$w; height=$h; bytes=([System.IO.FileInfo]::new($destination)).Length; rights='Project reference asset; no blanket reuse license is granted.'})
    } finally {
        if ($clip) { $clip.Dispose() }
        if ($parameters) { $parameters.Dispose() }
        if ($graphics) { $graphics.Dispose() }
        if ($bitmap) { $bitmap.Dispose() }
        $image.Dispose()
    }
}

Export-Art 'Pics/Start02.jpg' 'landscape.jpg' 1600 82
Export-Art 'Pics/Start02.jpg' 'landscape-small.jpg' 800 82
Export-Art 'Pics/Start01.jpg' 'mountains.jpg' 1200 84
Export-Art 'Pics/Start03.jpg' 'waterfall.jpg' 1000 84
Export-Art 'Pics/Screen01-1920-1080.jpg' 'seasontree-map.jpg' 1000 87
Export-Art 'Pics/Screen03-1920-1080.jpg' 'seasontree-city.jpg' 1000 87
Export-Art 'Pics/Screen04-1920-1080.jpg' 'ink-study.jpg' 960 85
Export-Art 'SanguoWebsite/LinyuanleWebSite2/Images2/GameSummary.jpg' 'classic-archive.jpg' 500 90
Export-Art 'SanguoWebsite/LinyuanleWebSite2/Images2/StratagemView.jpg' 'classic-map.jpg' 500 90
Export-Art 'SanguoWebsite/LinyuanleWebSite2/Images2/InnovatePlay.jpg' 'classic-city.jpg' 500 90
Export-Art 'Sanguo/SanguoSeason/Resources/Raw/Assets/favicon.png' 'sanguoseason.png' 128 -Circle
Export-Art 'Sanguo/SanguoSeason/Resources/Raw/Content/Textures/MainMenu/SeasonMain.png' 'site-mark.png' 128 -Circle
Export-Art 'Sanguo/ZHSan/Resources/Raw/Assets/favicon.png' 'zhsan.png' 128

# 共享预览图使用现有山水，不引入外部字体或图片服务。
Export-Art 'Pics/Start01.jpg' 'social.jpg' 1200 83
foreach ($name in @('creators-map.svg', 'ming-study.svg')) {
    $manifest.Add([ordered]@{file=$name; source="History/docs/assets/img/$name"; width=1200; height=600; bytes=([System.IO.FileInfo]::new((Join-Path $target $name))).Length; rights='Original site illustration; not game artwork or a historical source.'})
}
$json = ConvertTo-Json -InputObject $manifest.ToArray() -Depth 4
[System.IO.File]::WriteAllText((Join-Path $target 'sources.json'), $json, [System.Text.UTF8Encoding]::new($false))
$manifest | ForEach-Object { [pscustomobject]$_ } | Select-Object file, width, height, bytes | Format-Table -AutoSize
