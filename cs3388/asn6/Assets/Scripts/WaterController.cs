using UnityEngine;

[RequireComponent(typeof(Renderer))]
public class WaterController : MonoBehaviour
{
    [System.Serializable]
    public struct Wave
    {
        public Vector2 direction;
        public float amplitude;
        public float wavelength;
        public float speed;
        [Range(0f, 1.5f)] public float steepness;
        public float phase;
    }

    public const int MaxWaveCount = 8;

    private static readonly int PropWaveCount   = Shader.PropertyToID("_WaveCount");
    private static readonly int PropWaveDirAmp  = Shader.PropertyToID("_WaveDirAmp");
    private static readonly int PropWaveParams  = Shader.PropertyToID("_WaveParams");
    private static readonly int PropDetailTex   = Shader.PropertyToID("_DetailTex");
    private static readonly int PropDetailTiling = Shader.PropertyToID("_DetailTiling");
    private static readonly int PropDetailScroll = Shader.PropertyToID("_DetailScroll");
    private static readonly int PropDetailStr   = Shader.PropertyToID("_DetailStrength");

    [Header("Renderer / Material")]
    public Renderer targetRenderer;

    [Header("Wave Set")]
    public Wave[] waves = new Wave[]
    {
        new Wave { direction = new Vector2( 1.0f,  0.1f), amplitude = 0.60f, wavelength = 10.0f, speed = 1.30f, steepness = 0.45f, phase = 0.0f },
        new Wave { direction = new Vector2( 0.4f,  1.0f), amplitude = 0.35f, wavelength =  6.0f, speed = 1.80f, steepness = 0.35f, phase = 1.2f },
        new Wave { direction = new Vector2(-0.7f,  0.4f), amplitude = 0.22f, wavelength =  4.0f, speed = 2.20f, steepness = 0.25f, phase = 2.1f },
        new Wave { direction = new Vector2(-1.0f, -0.2f), amplitude = 0.15f, wavelength =  2.5f, speed = 3.10f, steepness = 0.15f, phase = 0.7f }
    };

    [Header("Detail Layer")]
    public Texture2D detailTexture;
    public Vector2 detailTiling  = new Vector2(6f, 6f);
    public Vector2 detailScroll  = new Vector2(0.05f, 0.03f);
    [Range(0f, 1f)] public float detailStrength = 0.08f;

    private MaterialPropertyBlock mpb;
    private Vector4[] waveDirAmpArray;
    private Vector4[] waveParamsArray;

    private void Reset()
    {
        targetRenderer = GetComponent<Renderer>();
    }

    private void Awake()
    {
        if (targetRenderer == null)
            targetRenderer = GetComponent<Renderer>();

        mpb             = new MaterialPropertyBlock();
        waveDirAmpArray = new Vector4[MaxWaveCount];
        waveParamsArray = new Vector4[MaxWaveCount];
    }

    private void Update()
    {
        PushToShader();
    }

    private void PushToShader()
    {
        if (targetRenderer == null) return;

        int count = Mathf.Min(waves != null ? waves.Length : 0, MaxWaveCount);

        for (int i = 0; i < count; i++)
        {
            Wave    w = waves[i];
            Vector2 d = w.direction.normalized;
            waveDirAmpArray[i] = new Vector4(d.x, d.y, w.amplitude, w.wavelength);
            waveParamsArray[i] = new Vector4(w.speed, w.steepness, w.phase, 0f);
        }

        for (int i = count; i < MaxWaveCount; i++)
        {
            waveDirAmpArray[i] = Vector4.zero;
            waveParamsArray[i] = Vector4.zero;
        }

        targetRenderer.GetPropertyBlock(mpb);
        mpb.SetInt(PropWaveCount, count);
        mpb.SetVectorArray(PropWaveDirAmp, waveDirAmpArray);
        mpb.SetVectorArray(PropWaveParams, waveParamsArray);

        if (detailTexture != null)
        {
            mpb.SetTexture(PropDetailTex, detailTexture);
            mpb.SetVector(PropDetailTiling, new Vector4(detailTiling.x, detailTiling.y, 0f, 0f));
            mpb.SetVector(PropDetailScroll, new Vector4(detailScroll.x, detailScroll.y, 0f, 0f));
            mpb.SetFloat(PropDetailStr, detailStrength);
        }

        targetRenderer.SetPropertyBlock(mpb);
    }

    public Vector3 SampleDisplacement(Vector2 worldXZ, float timeSeconds)
    {
        Vector3 disp = Vector3.zero;
        if (waves == null) return disp;

        int count = Mathf.Min(waves.Length, MaxWaveCount);

        for (int i = 0; i < count; i++)
        {
            Wave    w   = waves[i];
            Vector2 dir = w.direction.normalized;

            float k    = 2f * Mathf.PI / Mathf.Max(w.wavelength, 0.001f);
            float f    = k * Vector2.Dot(dir, worldXZ) - w.speed * timeSeconds + w.phase;
            float cosF = Mathf.Cos(f);
            float sinF = Mathf.Sin(f);
            float hDisp = w.steepness * w.amplitude * cosF;

            disp.x += dir.x * hDisp;
            disp.z += dir.y * hDisp;
            disp.y += w.amplitude * sinF;
        }

        return disp;
    }

    public float SampleHeight(Vector2 worldXZ, float timeSeconds)
    {
        return transform.position.y + SampleDisplacement(worldXZ, timeSeconds).y;
    }

    public Vector3 SampleWorldPosition(Vector2 worldXZ, float timeSeconds)
    {
        Vector3 basePos = new Vector3(worldXZ.x, transform.position.y, worldXZ.y);
        return basePos + SampleDisplacement(worldXZ, timeSeconds);
    }

    public Vector3 SampleNormal(Vector2 worldXZ, float timeSeconds, float eps = 0.2f)
    {
        Vector3 centre = SampleWorldPosition(worldXZ, timeSeconds);
        Vector3 px     = SampleWorldPosition(worldXZ + new Vector2(eps, 0f), timeSeconds);
        Vector3 pz     = SampleWorldPosition(worldXZ + new Vector2(0f, eps), timeSeconds);

        return Vector3.Cross(pz - centre, px - centre).normalized;
    }
}
