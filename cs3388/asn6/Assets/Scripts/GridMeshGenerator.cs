using UnityEngine;

[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
public class GridMeshGenerator : MonoBehaviour
{
    [Header("Grid Settings")]
    [Min(2)] public int xSegments = 100;
    [Min(2)] public int zSegments = 100;
    [Min(0.1f)] public float width  = 50f;
    [Min(0.1f)] public float length = 50f;

    [Header("UV Scale")]
    public float uvScale = 1f;

    [Header("Generation")]
    public bool generateOnStart = true;

    private MeshFilter meshFilter;
    private Mesh generatedMesh;

    private void Awake()
    {
        meshFilter = GetComponent<MeshFilter>();
    }

    private void Start()
    {
        if (generateOnStart)
            Generate();
    }

    [ContextMenu("Generate Grid Mesh")]
    public void Generate()
    {
        int vertsX     = xSegments + 1;
        int vertsZ     = zSegments + 1;
        int totalVerts = vertsX * vertsZ;

        bool use32 = totalVerts > 65535;

        Vector3[] vertices  = new Vector3[totalVerts];
        Vector2[] uvs       = new Vector2[totalVerts];
        int[]     triangles = new int[xSegments * zSegments * 6];

        float halfW = width  * 0.5f;
        float halfL = length * 0.5f;

        for (int z = 0; z < vertsZ; z++)
        {
            for (int x = 0; x < vertsX; x++)
            {
                int   idx = z * vertsX + x;
                float tx  = (float)x / xSegments;
                float tz  = (float)z / zSegments;

                vertices[idx] = new Vector3(tx * width - halfW, 0f, tz * length - halfL);
                uvs[idx]      = new Vector2(tx * uvScale, tz * uvScale);
            }
        }

        int ti = 0;
        for (int z = 0; z < zSegments; z++)
        {
            for (int x = 0; x < xSegments; x++)
            {
                int bl = z * vertsX + x;
                int br = bl + 1;
                int tl = bl + vertsX;
                int tr = tl + 1;

                triangles[ti++] = bl;
                triangles[ti++] = tl;
                triangles[ti++] = br;

                triangles[ti++] = br;
                triangles[ti++] = tl;
                triangles[ti++] = tr;
            }
        }

        if (generatedMesh == null)
            generatedMesh = new Mesh { name = "WaterGrid" };
        else
            generatedMesh.Clear();

        if (use32)
            generatedMesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;

        generatedMesh.vertices  = vertices;
        generatedMesh.uv        = uvs;
        generatedMesh.triangles = triangles;
        generatedMesh.RecalculateNormals();
        generatedMesh.RecalculateBounds();

        meshFilter.sharedMesh = generatedMesh;
    }
}
