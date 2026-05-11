Shader "Custom/Water"
{
    Properties
    {
        _ShallowColor ("Shallow Colour",  Color) = (0.18, 0.52, 0.70, 0.85)
        _DeepColor    ("Deep Colour",     Color) = (0.04, 0.18, 0.35, 0.95)
        _DepthRange   ("Depth Blend Range", Float) = 3.0
        _Ambient      ("Ambient",  Range(0,1)) = 0.18
        _Diffuse      ("Diffuse",  Range(0,1)) = 0.72
        _Specular     ("Specular", Range(0,1)) = 0.90
        _Shininess    ("Shininess", Float) = 128.0
        _SpecularColor("Specular Colour", Color) = (1,1,1,1)
        _DetailTex       ("Detail Texture", 2D)     = "white" {}
        _DetailTiling    ("Detail Tiling",  Vector) = (6,6,0,0)
        _DetailScroll    ("Detail Scroll",  Vector) = (0.05,0.03,0,0)
        _DetailStrength  ("Detail Strength", Range(0,1)) = 0.08
        [HideInInspector] _WaveCount ("Wave Count", Int) = 4
    }

    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" }
        LOD 300
        ZWrite On
        Blend SrcAlpha OneMinusSrcAlpha
        Cull Off

        Pass
        {
            Tags { "LightMode"="ForwardBase" }

            CGPROGRAM
            #pragma vertex   vert
            #pragma fragment frag
            #pragma multi_compile_fwdbase

            #include "UnityCG.cginc"
            #include "Lighting.cginc"
            #include "AutoLight.cginc"

            float4    _ShallowColor;
            float4    _DeepColor;
            float     _DepthRange;
            float     _Ambient;
            float     _Diffuse;
            float     _Specular;
            float     _Shininess;
            float4    _SpecularColor;
            sampler2D _DetailTex;
            float4    _DetailTiling;
            float4    _DetailScroll;
            float     _DetailStrength;
            int       _WaveCount;
            float4    _WaveDirAmp[8];
            float4    _WaveParams[8];

            float3 GerstnerWave(float2 xz, float t,
                                float2 dir, float amp,
                                float wl, float spd,
                                float steep, float ph)
            {
                float k    = 6.28318530718 / max(wl, 0.001);
                float f    = k * dot(dir, xz) - spd * t + ph;
                float hDisp = steep * amp * cos(f);
                return float3(dir.x * hDisp, amp * sin(f), dir.y * hDisp);
            }

            float3 SampleDisplacement(float2 xz, float t)
            {
                float3 d = float3(0, 0, 0);
                for (int i = 0; i < _WaveCount; ++i)
                {
                    float2 dir  = normalize(_WaveDirAmp[i].xy);
                    float  amp  = _WaveDirAmp[i].z;
                    float  wl   = _WaveDirAmp[i].w;
                    float  spd  = _WaveParams[i].x;
                    float  stp  = _WaveParams[i].y;
                    float  ph   = _WaveParams[i].z;
                    d += GerstnerWave(xz, t, dir, amp, wl, spd, stp, ph);
                }
                return d;
            }

            float3 SampleNormal(float2 xz, float t)
            {
                float  eps  = 0.2;
                float3 c    = SampleDisplacement(xz, t);
                float3 px   = SampleDisplacement(xz + float2(eps, 0), t);
                float3 pz   = SampleDisplacement(xz + float2(0, eps), t);
                float3 base = float3(xz.x, 0, xz.y);
                float3 tX   = (base + float3(eps,0,0) + px) - (base + c);
                float3 tZ   = (base + float3(0,0,eps) + pz) - (base + c);
                return normalize(cross(tZ, tX));
            }

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv     : TEXCOORD0;
            };

            struct v2f
            {
                float4 pos      : SV_POSITION;
                float3 worldPos : TEXCOORD0;
                float2 uv       : TEXCOORD1;
                float3 normal   : TEXCOORD2;
                float3 viewDir  : TEXCOORD3;
            };

            v2f vert(appdata v)
            {
                v2f o;
                float3 worldPos = mul(unity_ObjectToWorld, v.vertex).xyz;
                float  t        = _Time.y;

                float3 disp = SampleDisplacement(worldPos.xz, t);

                float2 detailUV = worldPos.xz * _DetailTiling.xy / 50.0 + _DetailScroll.xy * t;
                float  detailH  = (tex2Dlod(_DetailTex, float4(detailUV, 0, 0)).r - 0.5) * 2.0 * _DetailStrength;
                disp.y += detailH;

                worldPos += disp;

                o.pos      = mul(UNITY_MATRIX_VP, float4(worldPos, 1.0));
                o.worldPos = worldPos;
                o.uv       = v.uv;
                o.normal   = SampleNormal(worldPos.xz, t);
                o.viewDir  = normalize(_WorldSpaceCameraPos - worldPos);
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float3 N = normalize(i.normal);
                float3 V = normalize(i.viewDir);
                float3 L = normalize(_WorldSpaceLightPos0.xyz);
                float3 H = normalize(L + V);

                float3 ambient  = _Ambient * unity_AmbientSky.rgb;
                float3 diffuse  = _Diffuse * max(0.0, dot(N, L)) * _LightColor0.rgb;
                float3 specular = _Specular * pow(max(0.0, dot(N, H)), _Shininess) * _SpecularColor.rgb * _LightColor0.rgb;

                float  depthT    = saturate(-i.worldPos.y / max(_DepthRange, 0.001));
                float4 baseColor = lerp(_ShallowColor, _DeepColor, depthT);

                float2 detailUV     = i.worldPos.xz * _DetailTiling.xy / 50.0 + _DetailScroll.xy * _Time.y;
                float4 detailSample = tex2D(_DetailTex, detailUV);
                baseColor.rgb = lerp(baseColor.rgb, detailSample.rgb, _DetailStrength * 0.4);

                float fresnel = 1.0 - saturate(dot(N, V));
                float alpha   = saturate(baseColor.a + fresnel * 0.25);

                return float4((ambient + diffuse) * baseColor.rgb + specular, alpha);
            }

            ENDCG
        }
    }

    FallBack "Diffuse"
}
