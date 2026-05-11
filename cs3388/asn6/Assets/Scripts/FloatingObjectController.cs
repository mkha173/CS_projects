using UnityEngine;

public class FloatingObjectController : MonoBehaviour
{
    [Header("Water Reference")]
    public WaterController water;

    [Header("Sampling")]
    public Vector3 localSampleOffset = Vector3.zero;
    public float verticalOffset = 0.25f;

    [Header("Smoothing")]
    public float positionLerp = 6f;
    public float tiltLerp = 4f;

    [Header("Orientation")]
    public bool useSurfaceNormalForTilt = true;

    private void LateUpdate()
    {
        if (water == null) return;

        float t = Time.time;

        Vector3 worldSample = transform.TransformPoint(localSampleOffset);
        Vector2 xz = new Vector2(worldSample.x, worldSample.z);

        Vector3 waterPos = water.SampleWorldPosition(xz, t);

        Vector3 pos = transform.position;
        pos.y = Mathf.Lerp(pos.y, waterPos.y + verticalOffset, positionLerp * Time.deltaTime);
        transform.position = pos;

        if (useSurfaceNormalForTilt)
        {
            Vector3 normal = water.SampleNormal(xz, t);
            Quaternion targetRot = Quaternion.FromToRotation(Vector3.up, normal) *
                                   Quaternion.Euler(0f, transform.eulerAngles.y, 0f);
            transform.rotation = Quaternion.Slerp(transform.rotation, targetRot, tiltLerp * Time.deltaTime);
        }
    }
}
